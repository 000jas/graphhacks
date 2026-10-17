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


def discover_relationship_patterns(
    entity_id: str,
    max_depth: int = 3,
    min_frequency: int = 1,
    tenant_graph: str = "",
) -> dict[str, Any]:
    """
    Discover recurring multi-hop relationship patterns, indirect connections,
    and structural motifs around a given entity.
    """
    entity_id = validate_identifier(entity_id, field_name="entity_id")
    target_graph = settings.validate_graph_name(tenant_graph)
    depth = max(1, min(max_depth, 4))

    entity_rows = execute_ro_query(
        "MATCH (n:Entity {id: $id}) RETURN n.id, n.name, n.kind",
        params={"id": entity_id},
        graph_name=target_graph,
    )
    if not entity_rows:
        return {
            "found": False,
            "entity_id": entity_id,
            "message": f"Entity '{entity_id}' not found in graph.",
            "tenant_graph": target_graph,
        }

    e_id, e_name, e_kind = entity_rows[0]

    query = f"""
    MATCH p = (start:Entity {{id: $entity_id}})-[*1..{depth}]-(target:Entity)
    WHERE target.id <> start.id
    RETURN
        length(p) AS hop_length,
        [n IN nodes(p) | n.kind] AS kind_pattern,
        [r IN relationships(p) | type(r)] AS rel_pattern,
        target.id AS target_id,
        target.name AS target_name,
        target.kind AS target_kind
    LIMIT 250
    """
    rows = execute_ro_query(query, params={"entity_id": entity_id}, graph_name=target_graph)

    pattern_counts: dict[tuple, int] = defaultdict(int)
    pattern_examples: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    indirect_targets: dict[str, dict[str, Any]] = {}

    for hops, kinds, rels, t_id, t_name, t_kind in rows:
        pattern_key = (hops, tuple(kinds), tuple(rels))
        pattern_counts[pattern_key] += 1
        if len(pattern_examples[pattern_key]) < 3:
            pattern_examples[pattern_key].append({
                "target_id": t_id,
                "target_name": t_name,
                "target_kind": t_kind,
            })
        if hops >= 2 and t_id not in indirect_targets:
            indirect_targets[t_id] = {
                "id": t_id,
                "name": t_name,
                "kind": t_kind,
                "hops": hops,
            }

    patterns_list = []
    for (hops, kinds, rels), count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True):
        if count >= min_frequency:
            patterns_list.append({
                "depth": hops,
                "node_kind_sequence": list(kinds),
                "relationship_sequence": list(rels),
                "occurrences": count,
                "sample_targets": pattern_examples[(hops, kinds, rels)],
            })

    triangles_query = """
    MATCH (a:Entity {id: $entity_id})-[r1]-(b:Entity)-[r2]-(c:Entity)-[r3]-(a)
    WHERE b.id <> c.id AND b.id <> a.id AND c.id <> a.id
    RETURN DISTINCT b.id, b.name, b.kind, c.id, c.name, c.kind, type(r1), type(r2), type(r3)
    LIMIT 20
    """
    tri_rows = execute_ro_query(triangles_query, params={"entity_id": entity_id}, graph_name=target_graph)
    triangles = [
        {
            "intermediary_1": {"id": r[0], "name": r[1], "kind": r[2]},
            "intermediary_2": {"id": r[3], "name": r[4], "kind": r[5]},
            "connecting_relationships": [r[6], r[7], r[8]],
            "pattern": f"Triangular reinforcement between '{e_name}', '{r[1]}', and '{r[4]}'",
        }
        for r in tri_rows
    ]

    return {
        "found": True,
        "entity": {"id": e_id, "name": e_name, "kind": e_kind},
        "search_depth": depth,
        "total_distinct_patterns": len(patterns_list),
        "recurring_patterns": patterns_list[:15],
        "indirect_connections_count": len(indirect_targets),
        "indirect_connections_sample": list(indirect_targets.values())[:10],
        "triangular_motifs_count": len(triangles),
        "triangular_motifs": triangles[:5],
        "tenant_graph": target_graph,
    }


def find_common_neighbors(
    entity_ids: list[str],
    direction: str = "both",
    limit: int = 25,
    tenant_graph: str = "",
) -> dict[str, Any]:
    """
    Identify common entities, shared dependencies, people, or resources
    connecting two or more entities, with Jaccard similarity and Adamic-Adar scores.
    """
    if not entity_ids or len(entity_ids) < 2:
        raise ValueError("entity_ids must contain at least 2 distinct entity identifiers")
    if len(entity_ids) > 10:
        raise ValueError("entity_ids list cannot exceed 10 entities")

    clean_ids = [validate_identifier(eid, field_name="entity_id") for eid in entity_ids]
    target_graph = settings.validate_graph_name(tenant_graph)
    limit = max(1, min(limit, 50))

    dir_pattern = "-[r]->" if direction == "outgoing" else "<-[r]-" if direction == "incoming" else "-[r]-"

    entity_neighbors: dict[str, set[str]] = {}
    neighbor_details: dict[str, dict[str, Any]] = {}
    neighbor_connections: dict[str, list[dict[str, str]]] = defaultdict(list)

    for eid in clean_ids:
        query = f"""
        MATCH (start:Entity {{id: $eid}}){dir_pattern}(neighbor:Entity)
        WHERE neighbor.id <> start.id
        RETURN neighbor.id, neighbor.name, neighbor.kind, type(r), neighbor.status
        """
        rows = execute_ro_query(query, params={"eid": eid}, graph_name=target_graph)
        nbr_set = set()
        for n_id, n_name, n_kind, r_type, n_status in rows:
            nbr_set.add(n_id)
            if n_id not in neighbor_details:
                neighbor_details[n_id] = {
                    "id": n_id,
                    "name": n_name,
                    "kind": n_kind,
                    "status": n_status,
                }
            neighbor_connections[n_id].append({
                "from_entity_id": eid,
                "relationship_type": r_type,
            })
        entity_neighbors[eid] = nbr_set

    all_sets = list(entity_neighbors.values())
    common_all = set.intersection(*all_sets) if all_sets else set()
    union_all = set.union(*all_sets) if all_sets else set()

    pairwise_jaccard = {}
    for i in range(len(clean_ids)):
        for j in range(i + 1, len(clean_ids)):
            id_a, id_b = clean_ids[i], clean_ids[j]
            set_a, set_b = entity_neighbors[id_a], entity_neighbors[id_b]
            union_ab = set_a | set_b
            inter_ab = set_a & set_b
            score = round(len(inter_ab) / max(1, len(union_ab)), 4)
            pairwise_jaccard[f"{id_a} <-> {id_b}"] = {
                "shared_count": len(inter_ab),
                "total_union_count": len(union_ab),
                "jaccard_similarity": score,
            }

    scored_common = []
    for nid in common_all:
        deg_rows = execute_ro_query(
            "MATCH (n:Entity {id: $nid})-[r]-() RETURN count(r) AS degree",
            params={"nid": nid},
            graph_name=target_graph,
        )
        deg = deg_rows[0][0] if deg_rows else 1
        aa_score = round(1.0 / math.log(max(2, deg)), 4)
        info = neighbor_details[nid]

        scored_common.append({
            "id": nid,
            "name": info["name"],
            "kind": info["kind"],
            "status": info["status"],
            "total_degree": deg,
            "adamic_adar_weight": aa_score,
            "connected_via": neighbor_connections[nid],
        })

    scored_common.sort(key=lambda x: x["adamic_adar_weight"], reverse=True)

    return {
        "entity_ids": clean_ids,
        "direction": direction,
        "total_shared_neighbors": len(common_all),
        "pairwise_similarity": pairwise_jaccard,
        "shared_neighbors": scored_common[:limit],
        "interpretation": (
            f"Found {len(common_all)} common entities connecting {[eid for eid in clean_ids]}. "
            "High Adamic-Adar score indicates specific, non-trivial shared resources or dependencies rather than ubiquitous hub nodes."
        ),
        "tenant_graph": target_graph,
    }


def find_alternative_paths(
    source_id: str,
    target_id: str,
    max_depth: int = 6,
    max_paths: int = 5,
    relationship_types: Optional[list[str]] = None,
    tenant_graph: str = "",
) -> dict[str, Any]:
    """
    Discover multiple independent and alternative paths between two entities,
    evaluating path redundancy, bottlenecks, and edge evidence.
    """
    source_id = validate_identifier(source_id, field_name="source_id")
    target_id = validate_identifier(target_id, field_name="target_id")
    if source_id == target_id:
        raise ValueError("source_id and target_id must be distinct")

    depth = max(1, min(max_depth, 6))
    max_paths = max(1, min(max_paths, 10))
    target_graph = settings.validate_graph_name(tenant_graph)

    rel_types = relationship_types or []
    for r in rel_types:
        validate_relationship_type(r)

    rel_filter = ""
    params: dict[str, Any] = {"source_id": source_id, "target_id": target_id}
    if rel_types:
        rel_filter = "AND all(rel IN relationships(p) WHERE type(rel) IN $rels)"
        params["rels"] = rel_types

    query = f"""
    MATCH p = (source:Entity {{id: $source_id}})-[*1..{depth}]-(target:Entity {{id: $target_id}})
    WHERE true {rel_filter}
    RETURN p
    ORDER BY length(p)
    LIMIT {max_paths}
    """
    rows = execute_ro_query(query, params=params, graph_name=target_graph)

    if not rows:
        return {
            "found": False,
            "source_id": source_id,
            "target_id": target_id,
            "paths_count": 0,
            "message": f"No alternative paths found between '{source_id}' and '{target_id}' within depth {depth}.",
            "tenant_graph": target_graph,
        }

    paths = []
    all_intermediate_nodes: list[set[str]] = []

    for idx, row in enumerate(rows, start=1):
        path = row[0]
        node_map = {n.id: n.properties.get("id") for n in path.nodes()}

        path_nodes = [
            {
                "id": n.properties.get("id"),
                "name": n.properties.get("name"),
                "kind": n.properties.get("kind"),
            }
            for n in path.nodes()
        ]

        path_edges = [
            {
                "type": r.relation,
                "from_id": node_map.get(r.src_node),
                "to_id": node_map.get(r.dest_node),
                "source_record_id": r.properties.get("source_record_id"),
                "observed_at": r.properties.get("observed_at"),
                "confidence": r.properties.get("confidence", 1.0),
            }
            for r in path.edges()
        ]

        intermediate_ids = {n["id"] for n in path_nodes if n["id"] not in (source_id, target_id)}
        all_intermediate_nodes.append(intermediate_ids)

        path_confidence = 1.0
        for edge in path_edges:
            conf = edge.get("confidence")
            if isinstance(conf, (int, float)):
                path_confidence *= conf

        paths.append({
            "path_rank": idx,
            "hop_count": len(path_edges),
            "estimated_path_confidence": round(path_confidence, 4),
            "nodes": path_nodes,
            "edges": path_edges,
            "intermediate_node_ids": list(intermediate_ids),
        })

    disjoint_count = 1
    shared_intermediates: set[str] = set()
    if len(all_intermediate_nodes) > 1:
        for i in range(len(all_intermediate_nodes)):
            for j in range(i + 1, len(all_intermediate_nodes)):
                common = all_intermediate_nodes[i] & all_intermediate_nodes[j]
                shared_intermediates.update(common)
                if not common:
                    disjoint_count += 1

    return {
        "found": True,
        "source_id": source_id,
        "target_id": target_id,
        "paths_count": len(paths),
        "disjoint_paths_count": disjoint_count,
        "shared_bottlenecks_between_paths": list(shared_intermediates),
        "has_redundant_independent_path": disjoint_count >= 2,
        "paths": paths,
        "interpretation": (
            f"Identified {len(paths)} path(s). {disjoint_count} path(s) are node-disjoint. "
            f"Intermediaries {list(shared_intermediates)} appear in multiple paths and represent single points of failure."
            if shared_intermediates
            else f"Identified {len(paths)} independent, resilient alternative path(s)."
        ),
        "tenant_graph": target_graph,
    }


def analyze_reachability(
    start_entity_id: str,
    target_entity_ids: Optional[list[str]] = None,
    direction: str = "downstream",
    max_depth: int = 5,
    relationship_types: Optional[list[str]] = None,
    target_kinds: Optional[list[str]] = None,
    tenant_graph: str = "",
) -> dict[str, Any]:
    """
    Determine reachability from a start entity under direction, depth, relationship, and kind constraints.
    """
    start_entity_id = validate_identifier(start_entity_id, field_name="start_entity_id")
    target_graph = settings.validate_graph_name(tenant_graph)
    depth = max(1, min(max_depth, 6))

    clean_target_ids = [validate_identifier(tid, field_name="target_entity_id") for tid in (target_entity_ids or [])]
    clean_kinds = [validate_identifier(k, field_name="target_kind") for k in (target_kinds or [])]

    rel_types = relationship_types or []
    for r in rel_types:
        validate_relationship_type(r)

    dir_pattern = f"-[*1..{depth}]->" if direction == "downstream" else f"<-[*1..{depth}]-" if direction == "upstream" else f"-[*1..{depth}]-"

    path_filter = ""
    params: dict[str, Any] = {"start_id": start_entity_id}

    if rel_types:
        path_filter += " AND all(rel IN relationships(p) WHERE type(rel) IN $rels)"
        params["rels"] = rel_types
    if clean_kinds:
        path_filter += " AND reachable.kind IN $kinds"
        params["kinds"] = clean_kinds

    query = f"""
    MATCH p = (start:Entity {{id: $start_id}}){dir_pattern}(reachable:Entity)
    WHERE reachable.id <> start.id {path_filter}
    RETURN
        reachable.id,
        reachable.name,
        reachable.kind,
        reachable.status,
        min(length(p)) AS min_hops
    ORDER BY min_hops, reachable.name
    LIMIT 200
    """
    rows = execute_ro_query(query, params=params, graph_name=target_graph)

    reachable_entities = {}
    kind_distribution: dict[str, int] = defaultdict(int)
    hop_histogram: dict[int, int] = defaultdict(int)

    for r_id, r_name, r_kind, r_status, hops in rows:
        reachable_entities[r_id] = {
            "id": r_id,
            "name": r_name,
            "kind": r_kind,
            "status": r_status,
            "min_hops": hops,
        }
        kind_distribution[r_kind] += 1
        hop_histogram[hops] += 1

    target_evaluations = []
    if clean_target_ids:
        for tid in clean_target_ids:
            if tid in reachable_entities:
                target_evaluations.append({
                    "target_id": tid,
                    "reachable": True,
                    "min_hops": reachable_entities[tid]["min_hops"],
                    "entity": reachable_entities[tid],
                })
            else:
                t_check = execute_ro_query(
                    "MATCH (n:Entity {id: $id}) RETURN n.id, n.name, n.kind",
                    params={"id": tid},
                    graph_name=target_graph,
                )
                if not t_check:
                    reason = f"Target '{tid}' does not exist in graph."
                else:
                    reason = f"No path found within depth {depth} in direction '{direction}' with current relationship filters."
                target_evaluations.append({
                    "target_id": tid,
                    "reachable": False,
                    "reason": reason,
                })

    return {
        "start_entity_id": start_entity_id,
        "direction": direction,
        "max_depth_explored": depth,
        "total_reachable_entities": len(reachable_entities),
        "kind_distribution": dict(kind_distribution),
        "hop_histogram": dict(sorted(hop_histogram.items())),
        "specific_targets_evaluation": target_evaluations if clean_target_ids else None,
        "sample_reachable_entities": list(reachable_entities.values())[:30],
        "tenant_graph": target_graph,
    }


def detect_graph_anomalies(
    anomaly_types: Optional[list[str]] = None,
    tenant_graph: str = "",
) -> dict[str, Any]:
    """
    Detect structural anomalies, isolated nodes, unexpected high-degree spikes,
    duplicate-looking entities, and unverified relationships.
    """
    target_graph = settings.validate_graph_name(tenant_graph)
    anomalies: list[dict[str, Any]] = []

    isolated_rows = execute_ro_query(
        """
        MATCH (n:Entity)
        WHERE NOT (n)-[]-()
        RETURN n.id, n.name, n.kind, n.status
        LIMIT 20
        """,
        graph_name=target_graph,
    )
    if isolated_rows:
        anomalies.append({
            "anomaly_type": "ISOLATED_NODES",
            "severity": "MEDIUM",
            "count": len(isolated_rows),
            "description": f"Found {len(isolated_rows)} entity node(s) with 0 connections.",
            "entities": [{"id": r[0], "name": r[1], "kind": r[2]} for r in isolated_rows],
            "recommendation": "Investigate whether these entities are abandoned records or missing relationship ingestion.",
        })

    dup_rows = execute_ro_query(
        """
        MATCH (a:Entity), (b:Entity)
        WHERE a.id < b.id AND toLower(trim(a.name)) = toLower(trim(b.name))
        RETURN a.id, a.name, a.kind, b.id, b.name, b.kind
        LIMIT 20
        """,
        graph_name=target_graph,
    )
    if dup_rows:
        anomalies.append({
            "anomaly_type": "POTENTIAL_DUPLICATE_ENTITIES",
            "severity": "HIGH",
            "count": len(dup_rows),
            "description": f"Found {len(dup_rows)} pairs of entities with identical names but distinct IDs.",
            "pairs": [
                {"entity_1": {"id": r[0], "name": r[1], "kind": r[2]}, "entity_2": {"id": r[3], "name": r[4], "kind": r[5]}}
                for r in dup_rows
            ],
            "recommendation": "Perform entity resolution and merge records to avoid split evidence paths.",
        })

    degree_rows = execute_ro_query(
        """
        MATCH (n:Entity)-[r]-()
        WITH n, count(r) AS deg
        ORDER BY deg DESC
        RETURN n.id, n.name, n.kind, deg
        LIMIT 10
        """,
        graph_name=target_graph,
    )
    if degree_rows:
        degrees = [r[3] for r in degree_rows]
        avg_deg = sum(degrees) / len(degrees) if degrees else 0
        super_hubs = [
            {"id": r[0], "name": r[1], "kind": r[2], "degree": r[3]}
            for r in degree_rows
            if r[3] > max(15, avg_deg * 2.5)
        ]
        if super_hubs:
            anomalies.append({
                "anomaly_type": "HIGH_DEGREE_SPIKE_HUB",
                "severity": "LOW",
                "count": len(super_hubs),
                "description": f"Found {len(super_hubs)} super-connected hub nodes with disproportionate connectivity.",
                "hubs": super_hubs,
                "recommendation": "Review super-hubs to ensure they do not create query latency bottlenecks during multi-hop expansions.",
            })

    unverified_rows = execute_ro_query(
        """
        MATCH (a:Entity)-[r]->(b:Entity)
        WHERE (r.source_record_id IS NULL OR r.confidence < 0.6)
        RETURN a.id, type(r), b.id, r.source_record_id, r.confidence
        LIMIT 20
        """,
        graph_name=target_graph,
    )
    if unverified_rows:
        anomalies.append({
            "anomaly_type": "UNVERIFIED_RELATIONSHIPS",
            "severity": "MEDIUM",
            "count": len(unverified_rows),
            "description": f"Found {len(unverified_rows)} relationship(s) lacking source provenance or having low confidence (<0.6).",
            "samples": [
                {"from_id": r[0], "relationship": r[1], "to_id": r[2], "source_record_id": r[3], "confidence": r[4]}
                for r in unverified_rows[:5]
            ],
            "recommendation": "Attach source verification IDs and validate relationship credibility before making irreversible decisions.",
        })

    return {
        "tenant_graph": target_graph,
        "total_anomaly_categories": len(anomalies),
        "anomalies": anomalies,
        "clean_graph": len(anomalies) == 0,
        "interpretation": (
            "Graph contains zero major structural anomalies."
            if not anomalies
            else f"Identified {len(anomalies)} structural anomaly category(ies) requiring investigative attention."
        ),
    }


def compare_connectivity(
    source_a_id: str,
    source_b_id: str,
    target_id: str = "",
    tenant_graph: str = "",
) -> dict[str, Any]:
    """
    Compare how two entities or graph regions are connected, contrasting
    dependencies, shared neighbors, and structural positions.
    """
    source_a_id = validate_identifier(source_a_id, field_name="source_a_id")
    source_b_id = validate_identifier(source_b_id, field_name="source_b_id")
    target_graph = settings.validate_graph_name(tenant_graph)

    nodes_rows = execute_ro_query(
        "MATCH (n:Entity) WHERE n.id IN [$id_a, $id_b] RETURN n.id, n.name, n.kind",
        params={"id_a": source_a_id, "id_b": source_b_id},
        graph_name=target_graph,
    )
    info_map = {r[0]: {"id": r[0], "name": r[1], "kind": r[2]} for r in nodes_rows}
    if source_a_id not in info_map or source_b_id not in info_map:
        raise ValueError(f"One or both entities '{source_a_id}', '{source_b_id}' not found in graph.")

    deg_a = execute_ro_query(
        "MATCH (n:Entity {id: $id})-[r]-() RETURN count(r)",
        params={"id": source_a_id},
        graph_name=target_graph,
    )[0][0]
    deg_b = execute_ro_query(
        "MATCH (n:Entity {id: $id})-[r]-() RETURN count(r)",
        params={"id": source_b_id},
        graph_name=target_graph,
    )[0][0]

    nbrs_a = execute_ro_query(
        "MATCH (n:Entity {id: $id})-[r]-(m:Entity) RETURN m.id, m.name, m.kind, type(r)",
        params={"id": source_a_id},
        graph_name=target_graph,
    )
    nbrs_b = execute_ro_query(
        "MATCH (n:Entity {id: $id})-[r]-(m:Entity) RETURN m.id, m.name, m.kind, type(r)",
        params={"id": source_b_id},
        graph_name=target_graph,
    )

    set_a = {r[0]: {"id": r[0], "name": r[1], "kind": r[2], "rel": r[3]} for r in nbrs_a}
    set_b = {r[0]: {"id": r[0], "name": r[1], "kind": r[2], "rel": r[3]} for r in nbrs_b}

    shared_ids = set(set_a.keys()) & set(set_b.keys())
    unique_a_ids = set(set_a.keys()) - shared_ids
    unique_b_ids = set(set_b.keys()) - shared_ids

    target_comparison = None
    if target_id:
        tid = validate_identifier(target_id, field_name="target_id")
        dist_a = execute_ro_query(
            "MATCH p = (a:Entity {id: $aid})-[*1..6]-(t:Entity {id: $tid}) RETURN min(length(p))",
            params={"aid": source_a_id, "tid": tid},
            graph_name=target_graph,
        )
        dist_b = execute_ro_query(
            "MATCH p = (b:Entity {id: $bid})-[*1..6]-(t:Entity {id: $tid}) RETURN min(length(p))",
            params={"bid": source_b_id, "tid": tid},
            graph_name=target_graph,
        )
        hops_a = dist_a[0][0] if dist_a and dist_a[0][0] is not None else None
        hops_b = dist_b[0][0] if dist_b and dist_b[0][0] is not None else None

        target_comparison = {
            "target_id": tid,
            "entity_a_distance_hops": hops_a,
            "entity_b_distance_hops": hops_b,
            "closer_entity": source_a_id if (hops_a or 99) < (hops_b or 99) else source_b_id if (hops_b or 99) < (hops_a or 99) else "EQUAL",
        }

    return {
        "entity_a": info_map[source_a_id],
        "entity_b": info_map[source_b_id],
        "total_degree_comparison": {"entity_a_degree": deg_a, "entity_b_degree": deg_b},
        "shared_neighbors_count": len(shared_ids),
        "shared_neighbors": [set_a[nid] for nid in shared_ids],
        "unique_to_entity_a": [set_a[nid] for nid in unique_a_ids],
        "unique_to_entity_b": [set_b[nid] for nid in unique_b_ids],
        "target_comparison": target_comparison,
        "tenant_graph": target_graph,
    }
