from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Optional

try:
    from mcp_server.config import settings, validate_identifier, validate_relationship_type
    from mcp_server.db import execute_ro_query
except ImportError:
    from config import settings, validate_identifier, validate_relationship_type
    from db import execute_ro_query


def search_entities_advanced(
    query: str = "",
    kinds: Optional[list[str]] = None,
    statuses: Optional[list[str]] = None,
    property_filters: Optional[dict[str, Any]] = None,
    connected_to: str = "",
    has_relationship: str = "",
    limit: int = 20,
    offset: int = 0,
    tenant_graph: str = "",
) -> dict[str, Any]:
    """
    Search graph entities with multi-faceted filtering (query, kinds, statuses,
    custom properties, relationship constraints) and pagination.
    """
    target_graph = settings.validate_graph_name(tenant_graph)
    limit = max(1, min(limit, 50))
    offset = max(0, offset)

    where_clauses: list[str] = []
    params: dict[str, Any] = {}

    clean_query = query.strip()
    if clean_query:
        where_clauses.append("(toLower(n.name) CONTAINS toLower($q) OR toLower(n.id) CONTAINS toLower($q))")
        params["q"] = clean_query

    if kinds:
        clean_kinds = [validate_identifier(k, field_name="kind") for k in kinds]
        where_clauses.append("n.kind IN $kinds")
        params["kinds"] = clean_kinds

    if statuses:
        where_clauses.append("toLower(n.status) IN $statuses")
        params["statuses"] = [s.lower() for s in statuses]

    if property_filters:
        for idx, (prop_k, prop_v) in enumerate(property_filters.items()):
            param_key = f"prop_val_{idx}"
            where_clauses.append(f"n.{prop_k} = ${param_key}")
            params[param_key] = prop_v

    match_clause = "MATCH (n)"
    if connected_to:
        cid = validate_identifier(connected_to, field_name="connected_to")
        rel_type_str = f":{validate_relationship_type(has_relationship)}" if has_relationship else ""
        match_clause = f"MATCH (target)-[{rel_type_str}]-(n) WHERE (toString(id(target)) = $connected_to OR target.id = $connected_to OR target.name = $connected_to)"
        params["connected_to"] = cid

    where_stmt = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    count_cypher = f"""
    {match_clause}
    {where_stmt}
    RETURN count(DISTINCT n) AS total
    """
    count_rows = execute_ro_query(count_cypher, params=params, graph_name=target_graph)
    total_count = count_rows[0][0] if count_rows else 0

    page_cypher = f"""
    {match_clause}
    {where_stmt}
    RETURN DISTINCT coalesce(n.id, toString(id(n))), coalesce(n.name, n.id, toString(id(n))), coalesce(n.kind, labels(n)[0], 'Entity'), n.status, n.source_ref, properties(n)
    ORDER BY coalesce(n.name, n.id, toString(id(n)))
    SKIP {offset}
    LIMIT {limit}
    """
    page_rows = execute_ro_query(page_cypher, params=params, graph_name=target_graph)

    entities = [
        {
            "id": r[0],
            "name": r[1],
            "kind": r[2],
            "status": r[3],
            "source_ref": r[4],
            "properties": r[5],
        }
        for r in page_rows
    ]

    has_more = (offset + len(entities)) < total_count

    return {
        "total_count": total_count,
        "offset": offset,
        "limit": limit,
        "returned_count": len(entities),
        "has_more": has_more,
        "next_offset": (offset + limit) if has_more else None,
        "entities": entities,
        "tenant_graph": target_graph,
    }


def compare_entities(
    entity_ids: list[str],
    include_relationships: bool = True,
    tenant_graph: str = "",
) -> dict[str, Any]:
    """
    Perform a side-by-side comparison of 2 or more entities, contrasting their properties,
    incoming/outgoing connections, dependencies, and evidence provenance.
    """
    if not entity_ids or len(entity_ids) < 2:
        raise ValueError("entity_ids must contain at least 2 entity identifiers to compare")
    if len(entity_ids) > 6:
        raise ValueError("A maximum of 6 entities can be compared simultaneously")

    clean_ids = [validate_identifier(eid, field_name="entity_id") for eid in entity_ids]
    target_graph = settings.validate_graph_name(tenant_graph)

    profiles: dict[str, dict[str, Any]] = {}
    out_connections: dict[str, dict[str, dict[str, Any]]] = {}
    in_connections: dict[str, dict[str, dict[str, Any]]] = {}

    for eid in clean_ids:
        node_rows = execute_ro_query(
            "MATCH (n) WHERE (toString(id(n)) = $id OR n.id = $id OR n.name = $id) "
            "RETURN coalesce(n.id, toString(id(n))), coalesce(n.name, n.id, toString(id(n))), coalesce(n.kind, labels(n)[0], 'Entity'), n.status, properties(n)",
            params={"id": eid},
            graph_name=target_graph,
        )
        if not node_rows:
            profiles[eid] = {"found": False, "id": eid}
            continue

        r = node_rows[0]
        profiles[eid] = {
            "found": True,
            "id": r[0],
            "name": r[1],
            "kind": r[2],
            "status": r[3],
            "properties": r[4],
        }

        if include_relationships:
            out_rows = execute_ro_query(
                "MATCH (n)-[r]->(target) WHERE (toString(id(n)) = $id OR n.id = $id OR n.name = $id) "
                "RETURN type(r), coalesce(target.id, toString(id(target))), coalesce(target.name, target.id, toString(id(target))), coalesce(target.kind, labels(target)[0], 'Entity')",
                params={"id": eid},
                graph_name=target_graph,
            )
            out_connections[eid] = {
                f"{r[0]} -> {r[1]}": {"type": r[0], "target_id": r[1], "target_name": r[2], "target_kind": r[3]}
                for r in out_rows
            }

            in_rows = execute_ro_query(
                "MATCH (source)-[r]->(n) WHERE (toString(id(n)) = $id OR n.id = $id OR n.name = $id) "
                "RETURN type(r), coalesce(source.id, toString(id(source))), coalesce(source.name, source.id, toString(id(source))), coalesce(source.kind, labels(source)[0], 'Entity')",
                params={"id": eid},
                graph_name=target_graph,
            )
            in_connections[eid] = {
                f"{r[1]} -> {r[0]}": {"type": r[0], "source_id": r[1], "source_name": r[2], "source_kind": r[3]}
                for r in in_rows
            }

    all_keys = set()
    for eid, p in profiles.items():
        if p.get("found"):
            all_keys.update(p["properties"].keys())

    property_comparison = []
    for k in sorted(all_keys):
        values = {eid: profiles[eid]["properties"].get(k) if profiles[eid].get("found") else None for eid in clean_ids}
        all_same = len(set(str(v) for v in values.values())) == 1
        property_comparison.append({
            "property": k,
            "values": values,
            "is_identical": all_same,
        })

    rel_analysis = None
    if include_relationships:
        shared_out = set.intersection(*(set(out_connections[eid].keys()) for eid in clean_ids if eid in out_connections)) if out_connections else set()
        shared_in = set.intersection(*(set(in_connections[eid].keys()) for eid in clean_ids if eid in in_connections)) if in_connections else set()

        rel_analysis = {
            "shared_outgoing_connections": [list(out_connections.values())[0][k] for k in shared_out] if shared_out else [],
            "shared_incoming_connections": [list(in_connections.values())[0][k] for k in shared_in] if shared_in else [],
            "outgoing_counts_by_entity": {eid: len(out_connections.get(eid, {})) for eid in clean_ids},
            "incoming_counts_by_entity": {eid: len(in_connections.get(eid, {})) for eid in clean_ids},
        }

    return {
        "compared_entity_ids": clean_ids,
        "profiles": profiles,
        "property_comparison": property_comparison,
        "relationship_comparison": rel_analysis,
        "tenant_graph": target_graph,
    }


def investigate_entity_cluster(
    entity_ids: list[str],
    max_depth: int = 2,
    max_neighbors_per_entity: int = 15,
    tenant_graph: str = "",
) -> dict[str, Any]:
    """
    Explore a cluster of entities within a single bounded operation, finding mutual
    interconnections, shared dependencies, bridging nodes, and aggregated risks.
    """
    if not entity_ids:
        raise ValueError("entity_ids must not be empty")
    if len(entity_ids) > 10:
        raise ValueError("entity_ids list cannot exceed 10 entities")

    clean_ids = [validate_identifier(eid, field_name="entity_id") for eid in entity_ids]
    target_graph = settings.validate_graph_name(tenant_graph)
    depth = max(1, min(max_depth, 3))

    direct_edges_query = """
    MATCH (a)-[r]->(b)
    WHERE (a.id IN $eids OR toString(id(a)) IN $eids) AND (b.id IN $eids OR toString(id(b)) IN $eids)
    RETURN coalesce(a.id, toString(id(a))), coalesce(a.name, a.id, toString(id(a))), type(r), coalesce(b.id, toString(id(b))), coalesce(b.name, b.id, toString(id(b))), properties(r)
    """
    direct_rows = execute_ro_query(direct_edges_query, params={"eids": clean_ids}, graph_name=target_graph)
    internal_connections = [
        {
            "from_id": r[0],
            "from_name": r[1],
            "type": r[2],
            "to_id": r[3],
            "to_name": r[4],
            "evidence": r[5],
        }
        for r in direct_rows
    ]

    intermediary_query = f"""
    MATCH (a)-[r1]-(bridge)-[r2]-(b)
    WHERE (a.id IN $eids OR toString(id(a)) IN $eids) AND (b.id IN $eids OR toString(id(b)) IN $eids) AND id(a) < id(b)
      AND NOT (bridge.id IN $eids OR toString(id(bridge)) IN $eids)
    RETURN DISTINCT coalesce(bridge.id, toString(id(bridge))), coalesce(bridge.name, bridge.id, toString(id(bridge))), coalesce(bridge.kind, labels(bridge)[0], 'Entity'), coalesce(a.id, toString(id(a))), coalesce(b.id, toString(id(b))), type(r1), type(r2)
    LIMIT 30
    """
    bridge_rows = execute_ro_query(intermediary_query, params={"eids": clean_ids}, graph_name=target_graph)
    bridges = [
        {
            "bridge_entity": {"id": r[0], "name": r[1], "kind": r[2]},
            "connects": [r[3], r[4]],
            "relationships": [r[5], r[6]],
        }
        for r in bridge_rows
    ]

    blocked_query = """
    MATCH (cluster_node)-[r*1..2]->(risk)
    WHERE (cluster_node.id IN $eids OR toString(id(cluster_node)) IN $eids)
    RETURN DISTINCT coalesce(risk.id, toString(id(risk))), coalesce(risk.name, risk.id, toString(id(risk))), coalesce(risk.kind, labels(risk)[0], 'Entity'), risk.status, coalesce(cluster_node.id, toString(id(cluster_node)))
    LIMIT 20
    """
    risk_rows = execute_ro_query(blocked_query, params={"eids": clean_ids}, graph_name=target_graph)
    associated_risks = [
        {
            "risk_entity": {"id": r[0], "name": r[1], "kind": r[2], "status": r[3]},
            "affects_entity_id": r[4],
        }
        for r in risk_rows
    ]

    return {
        "cluster_entity_ids": clean_ids,
        "internal_relationships_count": len(internal_connections),
        "internal_connections": internal_connections,
        "shared_intermediaries_count": len(bridges),
        "shared_intermediaries": bridges,
        "identified_risks_and_prerequisites": associated_risks,
        "cohesion_assessment": (
            "High internal density" if len(internal_connections) >= len(clean_ids)
            else "Loosely coupled via intermediaries" if bridges
            else "Independent / largely disconnected entities"
        ),
        "tenant_graph": target_graph,
    }


def extract_investigation_subgraph(
    focal_entity_ids: list[str],
    max_depth: int = 2,
    max_nodes: int = 50,
    relationship_types: Optional[list[str]] = None,
    tenant_graph: str = "",
) -> dict[str, Any]:
    """
    Extract a compact, relevant, bounded subgraph around focal entities
    tailored for investigation context, visual inspection, and agent reasoning.
    """
    if not focal_entity_ids:
        raise ValueError("focal_entity_ids must contain at least one entity identifier")

    clean_focal = [validate_identifier(eid, field_name="focal_entity_id") for eid in focal_entity_ids]
    target_graph = settings.validate_graph_name(tenant_graph)
    depth = max(1, min(max_depth, 3))
    max_nodes = max(5, min(max_nodes, 100))

    rel_types = relationship_types or []
    for r in rel_types:
        validate_relationship_type(r)

    rel_filter = ""
    params: dict[str, Any] = {"focal_ids": clean_focal}
    if rel_types:
        rel_filter = "AND all(rel IN relationships(p) WHERE type(rel) IN $rels)"
        params["rels"] = rel_types

    query = f"""
    MATCH p = (focal)-[*1..{depth}]-(neighbor)
    WHERE (focal.id IN $focal_ids OR toString(id(focal)) IN $focal_ids) {rel_filter}
    RETURN p
    LIMIT 80
    """
    rows = execute_ro_query(query, params=params, graph_name=target_graph)

    nodes_dict: dict[str, dict[str, Any]] = {}
    edges_set = set()
    edges_list: list[dict[str, Any]] = []

    for fid in clean_focal:
        f_rows = execute_ro_query(
            "MATCH (n) WHERE (toString(id(n)) = $id OR n.id = $id OR n.name = $id) "
            "RETURN coalesce(n.id, toString(id(n))), coalesce(n.name, n.id, toString(id(n))), coalesce(n.kind, labels(n)[0], 'Entity'), n.status, properties(n)",
            params={"id": fid},
            graph_name=target_graph,
        )
        if f_rows:
            r = f_rows[0]
            nodes_dict[fid] = {
                "id": r[0],
                "name": r[1],
                "kind": r[2],
                "status": r[3],
                "is_focal": True,
                "properties": r[4],
            }

    for row in rows:
        path = row[0]
        node_map = {}
        for n in path.nodes():
            nid = n.properties.get("id") or str(n.id)
            node_map[n.id] = nid
            if nid not in nodes_dict and len(nodes_dict) < max_nodes:
                nodes_dict[nid] = {
                    "id": nid,
                    "name": n.properties.get("name") or nid,
                    "kind": n.properties.get("kind"),
                    "status": n.properties.get("status"),
                    "is_focal": nid in clean_focal,
                    "properties": n.properties,
                }

        for r in path.edges():
            src_id = node_map.get(r.src_node)
            dest_id = node_map.get(r.dest_node)
            if src_id in nodes_dict and dest_id in nodes_dict:
                edge_sig = (src_id, dest_id, r.relation)
                if edge_sig not in edges_set:
                    edges_set.add(edge_sig)
                    edges_list.append({
                        "from_id": src_id,
                        "to_id": dest_id,
                        "type": r.relation,
                        "source_record_id": r.properties.get("source_record_id"),
                        "observed_at": r.properties.get("observed_at"),
                        "confidence": r.properties.get("confidence", 1.0),
                    })

    return {
        "focal_entity_ids": clean_focal,
        "max_depth": depth,
        "node_count": len(nodes_dict),
        "edge_count": len(edges_list),
        "nodes": list(nodes_dict.values()),
        "edges": edges_list,
        "tenant_graph": target_graph,
    }


def compare_evidence_paths(
    source_id: str,
    target_id: str,
    candidate_paths_limit: int = 4,
    max_depth: int = 6,
    tenant_graph: str = "",
) -> dict[str, Any]:
    """
    Compare multiple candidate evidence paths between two entities, ranking them by
    hop distance, cumulative confidence score, verification rate, and freshness.
    """
    source_id = validate_identifier(source_id, field_name="source_id")
    target_id = validate_identifier(target_id, field_name="target_id")
    target_graph = settings.validate_graph_name(tenant_graph)
    depth = max(1, min(max_depth, 6))
    limit = max(1, min(candidate_paths_limit, 8))

    query = f"""
    MATCH p = (s)-[*1..{depth}]-(t)
    WHERE (toString(id(s)) = $source_id OR s.id = $source_id OR s.name = $source_id)
      AND (toString(id(t)) = $target_id OR t.id = $target_id OR t.name = $target_id)
    RETURN p
    ORDER BY length(p)
    LIMIT {limit}
    """
    rows = execute_ro_query(query, params={"source_id": source_id, "target_id": target_id}, graph_name=target_graph)

    if not rows:
        return {
            "found": False,
            "source_id": source_id,
            "target_id": target_id,
            "paths_evaluated": 0,
            "message": "No candidate evidence paths found.",
            "tenant_graph": target_graph,
        }

    evaluated_paths = []
    for idx, row in enumerate(rows, start=1):
        path = row[0]
        node_map = {n.id: n.properties.get("id") for n in path.nodes()}
        edges = []
        confidences = []
        verified_count = 0

        for r in path.edges():
            src = node_map.get(r.src_node)
            dst = node_map.get(r.dest_node)
            c = r.properties.get("confidence", 1.0)
            confidences.append(float(c) if isinstance(c, (int, float)) else 0.8)
            s_rec = r.properties.get("source_record_id")
            if s_rec:
                verified_count += 1

            edges.append({
                "type": r.relation,
                "from_id": src,
                "to_id": dst,
                "confidence": c,
                "source_record_id": s_rec,
                "observed_at": r.properties.get("observed_at"),
            })

        hops = len(edges)
        avg_confidence = round(sum(confidences) / max(1, len(confidences)), 4)
        cum_confidence = round(math.prod(confidences), 4)
        verif_rate = round(verified_count / max(1, hops), 2)

        composite_score = round((cum_confidence * 0.4 + verif_rate * 0.4 + (1.0 / max(1, hops)) * 0.2), 3)

        evaluated_paths.append({
            "candidate_rank": idx,
            "composite_score": composite_score,
            "hop_count": hops,
            "cumulative_confidence": cum_confidence,
            "average_edge_confidence": avg_confidence,
            "verification_rate": verif_rate,
            "is_fully_verified": verified_count == hops,
            "nodes": [n.properties.get("name") for n in path.nodes()],
            "edges": edges,
        })

    evaluated_paths.sort(key=lambda p: p["composite_score"], reverse=True)
    best_path = evaluated_paths[0]

    return {
        "found": True,
        "source_id": source_id,
        "target_id": target_id,
        "paths_evaluated": len(evaluated_paths),
        "strongest_path": best_path,
        "all_ranked_paths": evaluated_paths,
        "comparison_rationale": (
            f"Path with {best_path['hop_count']} hops and score {best_path['composite_score']} "
            f"(verification rate: {best_path['verification_rate'] * 100:.0f}%, confidence: {best_path['cumulative_confidence']}) "
            "provides the most reliable evidence connection."
        ),
        "tenant_graph": target_graph,
    }


def batch_get_entities(
    entity_ids: list[str],
    include_relationships: bool = False,
    tenant_graph: str = "",
) -> dict[str, Any]:
    """
    Retrieve multiple entities in a single efficient batch query.
    """
    if not entity_ids:
        raise ValueError("entity_ids must not be empty")
    if len(entity_ids) > 50:
        raise ValueError("entity_ids batch size cannot exceed 50")

    clean_ids = [validate_identifier(eid, field_name="entity_id") for eid in entity_ids]
    target_graph = settings.validate_graph_name(tenant_graph)

    query = """
    MATCH (n)
    WHERE (n.id IN $eids OR toString(id(n)) IN $eids OR n.name IN $eids)
    RETURN coalesce(n.id, toString(id(n))), coalesce(n.name, n.id, toString(id(n))), coalesce(n.kind, labels(n)[0], 'Entity'), n.status, n.source_ref, properties(n)
    """
    rows = execute_ro_query(query, params={"eids": clean_ids}, graph_name=target_graph)

    found_map = {}
    for r in rows:
        eid = r[0]
        found_map[eid] = {
            "id": r[0],
            "name": r[1],
            "kind": r[2],
            "status": r[3],
            "source_ref": r[4],
            "properties": r[5],
        }

    entities = [found_map[eid] for eid in clean_ids if eid in found_map]
    missing_ids = [eid for eid in clean_ids if eid not in found_map]

    return {
        "requested_count": len(clean_ids),
        "found_count": len(entities),
        "missing_ids": missing_ids,
        "entities": entities,
        "tenant_graph": target_graph,
    }


def generate_investigation_summary(
    investigation_title: str,
    entity_ids: list[str],
    tenant_graph: str = "",
) -> dict[str, Any]:
    """
    Synthesize graph investigation findings, distinguishing observed facts from
    derived connections and unresolved data gaps.
    """
    if not entity_ids:
        raise ValueError("entity_ids must contain at least one entity identifier")

    clean_ids = [validate_identifier(eid, field_name="entity_id") for eid in entity_ids]
    target_graph = settings.validate_graph_name(tenant_graph)

    batch_res = batch_get_entities(clean_ids, tenant_graph=target_graph)
    observed_facts = [
        {
            "id": e["id"],
            "name": e["name"],
            "kind": e["kind"],
            "status": e.get("status") or "Unknown",
            "provenance": e.get("source_ref") or "Unspecified",
            "classification": "FACT",
        }
        for e in batch_res["entities"]
    ]

    connections_query = """
    MATCH (a)-[r]->(b)
    WHERE (a.id IN $eids OR toString(id(a)) IN $eids) AND (b.id IN $eids OR toString(id(b)) IN $eids)
    RETURN coalesce(a.id, toString(id(a))), coalesce(a.name, a.id, toString(id(a))), type(r), coalesce(b.id, toString(id(b))), coalesce(b.name, b.id, toString(id(b))), r.source_record_id
    """
    conn_rows = execute_ro_query(connections_query, params={"eids": clean_ids}, graph_name=target_graph)
    derived_connections = [
        {
            "from_id": r[0],
            "from_name": r[1],
            "relationship": r[2],
            "to_id": r[3],
            "to_name": r[4],
            "source_record_id": r[5],
            "classification": "DERIVED",
        }
        for r in conn_rows
    ]

    unresolved_questions = []
    for missing_id in batch_res["missing_ids"]:
        unresolved_questions.append({
            "gap_type": "MISSING_ENTITY_RECORD",
            "entity_id": missing_id,
            "description": f"Entity '{missing_id}' was cited in the investigation but does not exist in the active graph.",
            "classification": "GAP",
        })

    for fact in observed_facts:
        if fact["status"] in ("delayed", "blocked", "awaiting_review", "pending"):
            unresolved_questions.append({
                "gap_type": "BLOCKING_STATUS",
                "entity_id": fact["id"],
                "description": f"'{fact['name']}' has unresolved status '{fact['status']}'.",
                "classification": "GAP",
            })

    next_steps = []
    if any(f["status"] == "delayed" for f in observed_facts):
        next_steps.append("Run 'analyze_graph_impact' on delayed entities to determine downstream release blockers.")
    if len(derived_connections) < len(clean_ids) - 1:
        next_steps.append("Execute 'find_alternative_paths' or 'find_common_neighbors' to uncover indirect connecting dependencies.")
    next_steps.append("Verify evidence quality using 'evaluate_evidence_quality' before taking action.")

    return {
        "investigation_title": investigation_title or "GraphOS Investigation Summary",
        "investigated_entities_count": len(clean_ids),
        "observed_facts": observed_facts,
        "derived_connections": derived_connections,
        "unresolved_questions_and_gaps": unresolved_questions,
        "recommended_next_investigation_steps": next_steps,
        "tenant_graph": target_graph,
    }
