from __future__ import annotations

import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

SERVER_DIR = Path(__file__).resolve().parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from mcp.server import MCPServer

try:
    from mcp_server.algorithms import (
        detect_critical_dependencies as detect_crit_deps,
        run_betweenness_centrality,
        run_closeness_centrality,
        run_community_detection as run_comm_detection,
        run_connected_components,
        run_cycle_detection,
        run_degree_centrality,
        run_pagerank,
    )
    from mcp_server.config import (
        SAFE_RELATIONSHIP_PATTERN,
        settings,
        validate_identifier,
        validate_relationship_type,
    )
    from mcp_server.counterfactual import (
        evaluate_candidate_actions as eval_candidate_actions,
        simulate_candidate_action,
    )
    from mcp_server.db import execute_ro_query
    from mcp_server.decision_memory import (
        execute_approved_action as exec_approved_action,
        propose_action as prop_action,
        query_decision_memory as query_dec_memory,
        record_investigation_finding as rec_inv_finding,
        record_outcome as rec_outcome,
        supersede_finding as sup_finding,
    )
    from mcp_server.evidence_quality import (
        detect_conflicting_evidence as detect_conflicts,
        evaluate_evidence_quality as eval_evidence_quality,
        inspect_temporal_graph as insp_temporal_graph,
    )
    from mcp_server.impact import (
        analyze_graph_impact as analyze_impact,
        assess_change_risk_and_impact as assess_change_impact,
    )
    from mcp_server.intelligence import (
        analyze_reachability as analyze_reach,
        compare_connectivity as comp_connectivity,
        detect_graph_anomalies as detect_anomalies,
        discover_relationship_patterns as disc_rel_patterns,
        find_alternative_paths as find_alt_paths,
        find_common_neighbors as find_com_neighbors,
    )
    from mcp_server.investigation import (
        batch_get_entities as batch_get_ents,
        compare_entities as comp_entities,
        compare_evidence_paths as comp_evidence_paths,
        extract_investigation_subgraph as extract_subgraph,
        generate_investigation_summary as gen_inv_summary,
        investigate_entity_cluster as inv_cluster,
        search_entities_advanced as search_ents_advanced,
    )
    from mcp_server.models import serialize_json
    from mcp_server.policy import check_action_policy
    from mcp_server.schema_discovery import discover_graph_schema as disc_schema
except ImportError:
    from algorithms import (
        detect_critical_dependencies as detect_crit_deps,
        run_betweenness_centrality,
        run_closeness_centrality,
        run_community_detection as run_comm_detection,
        run_connected_components,
        run_cycle_detection,
        run_degree_centrality,
        run_pagerank,
    )
    from config import (
        SAFE_RELATIONSHIP_PATTERN,
        settings,
        validate_identifier,
        validate_relationship_type,
    )
    from counterfactual import (
        evaluate_candidate_actions as eval_candidate_actions,
        simulate_candidate_action,
    )
    from db import execute_ro_query
    from decision_memory import (
        execute_approved_action as exec_approved_action,
        propose_action as prop_action,
        query_decision_memory as query_dec_memory,
        record_investigation_finding as rec_inv_finding,
        record_outcome as rec_outcome,
        supersede_finding as sup_finding,
    )
    from evidence_quality import (
        detect_conflicting_evidence as detect_conflicts,
        evaluate_evidence_quality as eval_evidence_quality,
        inspect_temporal_graph as insp_temporal_graph,
    )
    from impact import (
        analyze_graph_impact as analyze_impact,
        assess_change_risk_and_impact as assess_change_impact,
    )
    from intelligence import (
        analyze_reachability as analyze_reach,
        compare_connectivity as comp_connectivity,
        detect_graph_anomalies as detect_anomalies,
        discover_relationship_patterns as disc_rel_patterns,
        find_alternative_paths as find_alt_paths,
        find_common_neighbors as find_com_neighbors,
    )
    from investigation import (
        batch_get_entities as batch_get_ents,
        compare_entities as comp_entities,
        compare_evidence_paths as comp_evidence_paths,
        extract_investigation_subgraph as extract_subgraph,
        generate_investigation_summary as gen_inv_summary,
        investigate_entity_cluster as inv_cluster,
        search_entities_advanced as search_ents_advanced,
    )
    from models import serialize_json
    from policy import check_action_policy
    from schema_discovery import discover_graph_schema as disc_schema

logger = logging.getLogger("graphos.mcp.server")

mcp = MCPServer(
    name="GraphOS",
    instructions=(
        "GraphOS Evidence-Bound MCP Server: Exposes structured graph intelligence, multi-hop evidence paths, "
        "graph algorithms, blast radius analysis, counterfactual simulations, policy enforcement, "
        "and durable organizational memory over a cloud-hosted FalkorDB instance."
    ),
)

def entity_row(row: list[Any]) -> dict[str, Any]:
    res = {
        "id": row[0],
        "name": row[1],
        "kind": row[2],
        "status": row[3],
        "source_ref": row[4],
    }
    if len(row) > 5 and isinstance(row[5], dict):
        res["properties"] = row[5]
    return res


@mcp.tool()
def search_connected_entities(
    query: str = "",
    limit: int = 10,
    kind: str = "",
    tenant_graph: str = "",
) -> str:
    """
    Search graph entities across any property, identifier, or classification without schema assumptions.
    """
    start_t = time.perf_counter()
    query = (query or "").strip()
    kind = (kind or "").strip()
    if len(query) > 200:
        raise ValueError("query must be at most 200 characters")

    limit = max(1, min(limit, 25))
    target_graph = settings.validate_graph_name(tenant_graph)

    where_clauses: list[str] = []
    params: dict[str, Any] = {}
    if query:
        where_clauses.append(
            "(toLower(coalesce(n.name, n.title, n.label, n.id, n.code, n.key, '')) CONTAINS toLower($query) "
            "OR any(k IN keys(n) WHERE toLower(toString(n[k])) CONTAINS toLower($query)))"
        )
        params["query"] = query

    if kind:
        where_clauses.append("(n.kind = $kind OR $kind IN labels(n))")
        params["kind"] = kind

    where_stmt = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    cypher = f"""
    MATCH (n)
    {where_stmt}
    RETURN coalesce(n.id, n.code, n.key, toString(id(n))) AS id,
           coalesce(n.name, n.title, n.label, n.id, toString(id(n))) AS name,
           coalesce(n.kind, head([lbl IN labels(n) WHERE lbl <> 'Entity']), head(labels(n)), 'Node') AS kind,
           coalesce(n.status, n.state, 'UNKNOWN') AS status,
           coalesce(n.source_ref, n.source, 'discovered') AS source_ref,
           properties(n) AS properties
    ORDER BY coalesce(n.name, n.title, n.id, toString(id(n)))
    LIMIT {limit}
    """
    rows = execute_ro_query(cypher, params=params, graph_name=target_graph)

    res = {
        "query": query,
        "count": len(rows),
        "entities": [entity_row(row) for row in rows],
        "tenant_graph": target_graph,
    }
    logger.debug("search_connected_entities executed in %.2fms", (time.perf_counter() - start_t) * 1000)
    return serialize_json(res)


@mcp.tool()
def get_entity_profile(
    entity_id: str,
    tenant_graph: str = "",
) -> str:
    """
    Retrieve comprehensive intelligence for a specific entity including properties,
    source provenance references, connectivity status, and both incoming and outgoing relationships.
    """
    entity_id = entity_id.strip()
    if not entity_id:
        raise ValueError("entity_id must not be empty")

    target_graph = settings.validate_graph_name(tenant_graph)

    rows = execute_ro_query(
        """
        MATCH (n)
        WHERE toString(id(n)) = $entity_id
           OR n.id = $entity_id
           OR n.code = $entity_id
           OR n.key = $entity_id
           OR n.name = $entity_id
           OR any(k IN keys(n) WHERE toString(n[k]) = $entity_id)
        RETURN coalesce(n.id, n.code, n.key, toString(id(n))),
               coalesce(n.name, n.title, n.label, n.id, toString(id(n))),
               coalesce(n.kind, head([lbl IN labels(n) WHERE lbl <> 'Entity']), head(labels(n)), 'Node'),
               labels(n),
               properties(n),
               toString(id(n))
        LIMIT 1
        """,
        params={"entity_id": entity_id},
        graph_name=target_graph,
    )

    if not rows:
        return serialize_json({
            "found": False,
            "entity_id": entity_id,
            "tenant_graph": target_graph,
        })

    row = rows[0]
    nid = row[5]

    outgoing = execute_ro_query(
        """
        MATCH (n)-[r]->(other)
        WHERE toString(id(n)) = $nid
        RETURN type(r),
               coalesce(other.id, other.code, other.key, toString(id(other))),
               coalesce(other.name, other.title, other.label, other.id, toString(id(other))),
               coalesce(other.kind, head([lbl IN labels(other) WHERE lbl <> 'Entity']), head(labels(other)), 'Node'),
               properties(r),
               labels(other),
               properties(other)
        LIMIT 50
        """,
        params={"nid": nid},
        graph_name=target_graph,
    )

    incoming = execute_ro_query(
        """
        MATCH (other)-[r]->(n)
        WHERE toString(id(n)) = $nid
        RETURN type(r),
               coalesce(other.id, other.code, other.key, toString(id(other))),
               coalesce(other.name, other.title, other.label, other.id, toString(id(other))),
               coalesce(other.kind, head([lbl IN labels(other) WHERE lbl <> 'Entity']), head(labels(other)), 'Node'),
               properties(r),
               labels(other),
               properties(other)
        LIMIT 50
        """,
        params={"nid": nid},
        graph_name=target_graph,
    )

    is_isolated = len(outgoing) == 0 and len(incoming) == 0
    total_rels = len(outgoing) + len(incoming)
    exploration_status = "complete" if (len(outgoing) < 50 and len(incoming) < 50) else "partial"

    return serialize_json({
        "found": True,
        "entity": {
            "id": row[0],
            "name": row[1],
            "kind": row[2],
            "labels": row[3],
            "properties": row[4],
        },
        "outgoing_relationships": [
            {
                "type": r[0],
                "target": {"id": r[1], "name": r[2], "kind": r[3], "labels": r[5], "properties": r[6]},
                "evidence": r[4],
            }
            for r in outgoing
        ],
        "incoming_relationships": [
            {
                "type": r[0],
                "source": {"id": r[1], "name": r[2], "kind": r[3], "labels": r[5], "properties": r[6]},
                "evidence": r[4],
            }
            for r in incoming
        ],
        "is_isolated": is_isolated,
        "total_connected_relationships": total_rels,
        "relationship_exploration_status": exploration_status,
        "tenant_graph": target_graph,
    })


@mcp.tool()
def inspect_entity_neighbors(
    entity_id: str,
    direction: str = "both",
    relationship_types: Optional[list[str]] = None,
    limit: int = 25,
    tenant_graph: str = "",
) -> str:
    """
    Inspect immediate neighboring entities and connected relationships for an arbitrary entity.
    Returns actual adjacent nodes, relationship types, edge properties, and connectivity summary.
    Supports direction ('both', 'outgoing', 'incoming') and optional relationship type filtering.
    """
    entity_id = entity_id.strip()
    if not entity_id:
        raise ValueError("entity_id must not be empty")

    dir_clean = (direction or "both").strip().lower()
    if dir_clean not in ("both", "outgoing", "incoming"):
        dir_clean = "both"

    limit = max(1, min(limit, 50))
    target_graph = settings.validate_graph_name(tenant_graph)

    rel_types = relationship_types or []
    for r in rel_types:
        if not SAFE_RELATIONSHIP_PATTERN.fullmatch(r):
            raise ValueError(f"Invalid relationship type format: {r}")

    find_rows = execute_ro_query(
        """
        MATCH (n)
        WHERE toString(id(n)) = $entity_id
           OR n.id = $entity_id
           OR n.code = $entity_id
           OR n.key = $entity_id
           OR n.name = $entity_id
           OR any(k IN keys(n) WHERE toString(n[k]) = $entity_id)
        RETURN coalesce(n.id, n.code, n.key, toString(id(n))),
               coalesce(n.name, n.title, n.label, n.id, toString(id(n))),
               coalesce(n.kind, head([lbl IN labels(n) WHERE lbl <> 'Entity']), head(labels(n)), 'Node'),
               labels(n),
               properties(n),
               toString(id(n))
        LIMIT 1
        """,
        params={"entity_id": entity_id},
        graph_name=target_graph,
    )

    if not find_rows:
        return serialize_json({
            "found": False,
            "entity_id": entity_id,
            "message": f"Entity '{entity_id}' not found in graph '{target_graph}'.",
            "tenant_graph": target_graph,
        })

    f_row = find_rows[0]
    nid = f_row[5]

    # Query connected relationship types summary
    rel_type_summary_rows = execute_ro_query(
        """
        MATCH (n)-[r]-(other)
        WHERE toString(id(n)) = $nid
        RETURN type(r), count(r)
        ORDER BY count(r) DESC
        """,
        params={"nid": nid},
        graph_name=target_graph,
    )
    connected_rel_types = [
        {"relationship_type": r[0], "count": r[1]}
        for r in rel_type_summary_rows
    ]

    rel_filter = ""
    filter_params: dict[str, Any] = {"nid": nid}
    if rel_types:
        rel_filter = "AND type(r) IN $rel_types"
        filter_params["rel_types"] = rel_types

    neighbors: list[dict[str, Any]] = []

    if dir_clean in ("both", "outgoing"):
        out_rows = execute_ro_query(
            f"""
            MATCH (n)-[r]->(other)
            WHERE toString(id(n)) = $nid
            {rel_filter}
            RETURN type(r),
                   properties(r),
                   coalesce(other.id, other.code, other.key, toString(id(other))),
                   coalesce(other.name, other.title, other.label, other.id, toString(id(other))),
                   coalesce(other.kind, head([lbl IN labels(other) WHERE lbl <> 'Entity']), head(labels(other)), 'Node'),
                   labels(other),
                   properties(other)
            LIMIT {limit}
            """,
            params=filter_params,
            graph_name=target_graph,
        )
        for r in out_rows:
            neighbors.append({
                "direction": "outgoing",
                "relationship_type": r[0],
                "relationship_properties": r[1],
                "neighbor": {
                    "id": r[2],
                    "name": r[3],
                    "kind": r[4],
                    "labels": r[5],
                    "properties": r[6],
                },
            })

    if dir_clean in ("both", "incoming") and len(neighbors) < limit:
        remaining = limit - len(neighbors)
        in_rows = execute_ro_query(
            f"""
            MATCH (other)-[r]->(n)
            WHERE toString(id(n)) = $nid
            {rel_filter}
            RETURN type(r),
                   properties(r),
                   coalesce(other.id, other.code, other.key, toString(id(other))),
                   coalesce(other.name, other.title, other.label, other.id, toString(id(other))),
                   coalesce(other.kind, head([lbl IN labels(other) WHERE lbl <> 'Entity']), head(labels(other)), 'Node'),
                   labels(other),
                   properties(other)
            LIMIT {remaining}
            """,
            params=filter_params,
            graph_name=target_graph,
        )
        for r in in_rows:
            neighbors.append({
                "direction": "incoming",
                "relationship_type": r[0],
                "relationship_properties": r[1],
                "neighbor": {
                    "id": r[2],
                    "name": r[3],
                    "kind": r[4],
                    "labels": r[5],
                    "properties": r[6],
                },
            })

    total_connections = sum(r[1] for r in rel_type_summary_rows)
    is_isolated = total_connections == 0
    contract = "complete" if total_connections <= limit else "partial"

    return serialize_json({
        "found": True,
        "entity": {
            "id": f_row[0],
            "name": f_row[1],
            "kind": f_row[2],
            "labels": f_row[3],
            "properties": f_row[4],
        },
        "direction": dir_clean,
        "total_connections": total_connections,
        "connected_relationship_types": connected_rel_types,
        "neighbors_count": len(neighbors),
        "neighbors": neighbors,
        "is_isolated": is_isolated,
        "relationship_contract": contract,
        "tenant_graph": target_graph,
    })


@mcp.tool()
def traverse_relationships(
    entity_id: str,
    relationship_types: Optional[list[str]] = None,
    depth: int = 2,
    limit: int = 20,
    tenant_graph: str = "",
) -> str:
    """
    Explore multi-hop connected entities and return structured path chains with edge evidence.
    Traverses arbitrary relationships across the connected graph without schema assumptions.
    """
    entity_id = entity_id.strip()
    if not entity_id:
        raise ValueError("entity_id must not be empty")

    if not 1 <= depth <= 4:
        raise ValueError("depth must be between 1 and 4")

    limit = max(1, min(limit, 50))
    target_graph = settings.validate_graph_name(tenant_graph)

    start_rows = execute_ro_query(
        """
        MATCH (n)
        WHERE toString(id(n)) = $entity_id
           OR n.id = $entity_id
           OR n.code = $entity_id
           OR n.key = $entity_id
           OR n.name = $entity_id
           OR any(k IN keys(n) WHERE toString(n[k]) = $entity_id)
        RETURN toString(id(n)), coalesce(n.id, n.code, n.key, toString(id(n)))
        LIMIT 1
        """,
        params={"entity_id": entity_id},
        graph_name=target_graph,
    )

    if not start_rows:
        return serialize_json({
            "found": False,
            "start_entity_id": entity_id,
            "depth_limit": depth,
            "count": 0,
            "paths": [],
            "message": f"Entity '{entity_id}' not found in graph.",
            "tenant_graph": target_graph,
        })

    start_nid = start_rows[0][0]
    resolved_start_id = start_rows[0][1]

    rel_types = relationship_types or []
    for r in rel_types:
        if not SAFE_RELATIONSHIP_PATTERN.fullmatch(r):
            raise ValueError(f"Invalid relationship type format: {r}")

    path_filter = ""
    params: dict[str, Any] = {"start_nid": start_nid}

    if rel_types:
        path_filter = """
          AND all(rel IN relationships(p)
                  WHERE type(rel) IN $relationship_types)
        """
        params["relationship_types"] = rel_types

    query = f"""
    MATCH p = (start)-[*1..{depth}]-(neighbor)
    WHERE toString(id(start)) = $start_nid
      AND toString(id(neighbor)) <> $start_nid
    {path_filter}
    RETURN
        coalesce(neighbor.id, neighbor.code, neighbor.key, toString(id(neighbor))),
        coalesce(neighbor.name, neighbor.title, neighbor.label, neighbor.id, toString(id(neighbor))),
        coalesce(neighbor.kind, head([lbl IN labels(neighbor) WHERE lbl <> 'Entity']), head(labels(neighbor)), 'Node'),
        length(p),
        [node IN nodes(p) |
            {{
                id: coalesce(node.id, node.code, node.key, toString(id(node))),
                name: coalesce(node.name, node.title, node.label, node.id, toString(id(node))),
                kind: coalesce(node.kind, head([lbl IN labels(node) WHERE lbl <> 'Entity']), head(labels(node)), 'Node')
            }}]
            AS path_nodes,
        [rel IN relationships(p) |
            {{
                type: type(rel),
                source_record_id: rel.source_record_id,
                observed_at: rel.observed_at,
                confidence: rel.confidence,
                properties: properties(rel)
            }}]
            AS path_edges
    ORDER BY length(p), coalesce(neighbor.name, neighbor.id, toString(id(neighbor)))
    LIMIT {limit}
    """
    rows = execute_ro_query(query, params=params, graph_name=target_graph)

    paths = [
        {
            "entity": {"id": r[0], "name": r[1], "kind": r[2]},
            "depth": r[3],
            "path_nodes": r[4],
            "path_edges": r[5],
        }
        for r in rows
    ]

    return serialize_json({
        "found": True,
        "start_entity_id": resolved_start_id,
        "depth_limit": depth,
        "count": len(paths),
        "paths": paths,
        "tenant_graph": target_graph,
    })


@mcp.tool()
def find_shortest_evidence_path(
    source_id: str,
    target_id: str,
    max_depth: int = 8,
    tenant_graph: str = "",
) -> str:
    """
    Discover the shortest verifiable connection chain between two entities,
    capturing intermediate entities, relationship directions, and edge provenance.
    """
    source_id = source_id.strip()
    target_id = target_id.strip()
    if not source_id or not target_id:
        raise ValueError("source_id and target_id must not be empty")

    if not 1 <= max_depth <= 8:
        raise ValueError("max_depth must be between 1 and 8")

    target_graph = settings.validate_graph_name(tenant_graph)

    query = f"""
    MATCH p = (source)-[*1..{max_depth}]-(target)
    WHERE (source.id = $source_id OR source.code = $source_id OR source.key = $source_id OR toString(id(source)) = $source_id OR source.name = $source_id OR any(k IN keys(source) WHERE toString(source[k]) = $source_id))
      AND (target.id = $target_id OR target.code = $target_id OR target.key = $target_id OR toString(id(target)) = $target_id OR target.name = $target_id OR any(k IN keys(target) WHERE toString(target[k]) = $target_id))
    RETURN p
    ORDER BY length(p)
    LIMIT 1
    """
    rows = execute_ro_query(query, params={"source_id": source_id, "target_id": target_id}, graph_name=target_graph)

    if not rows:
        return serialize_json({
            "found": False,
            "source_id": source_id,
            "target_id": target_id,
            "message": "No path was found within the depth limit.",
            "tenant_graph": target_graph,
        })

    path = rows[0][0]
    node_map = {
        n.id: (
            n.properties.get("id")
            or n.properties.get("code")
            or n.properties.get("key")
            or str(n.id)
        )
        for n in path.nodes()
    }
    path_nodes = [
        {
            "id": (
                n.properties.get("id")
                or n.properties.get("code")
                or n.properties.get("key")
                or str(n.id)
            ),
            "name": (
                n.properties.get("name")
                or n.properties.get("title")
                or n.properties.get("label")
                or n.properties.get("id")
                or str(n.id)
            ),
            "kind": (
                n.properties.get("kind")
                or (
                    [lbl for lbl in n.labels if lbl != "Entity"][0]
                    if any(lbl != "Entity" for lbl in n.labels)
                    else (n.labels[0] if n.labels else "Node")
                )
            ),
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
            "confidence": r.properties.get("confidence"),
        }
        for r in path.edges()
    ]

    return serialize_json({
        "found": True,
        "source_id": source_id,
        "target_id": target_id,
        "path_nodes": path_nodes,
        "path_edges": path_edges,
        "hop_count": len(path_edges),
        "tenant_graph": target_graph,
    })


@mcp.tool()
def run_graph_algorithm(
    algorithm: str,
    entity_kinds: Optional[list[str]] = None,
    relationship_types: Optional[list[str]] = None,
    max_iterations: int = 25,
    top_k: int = 10,
    tenant_graph: str = "",
) -> str:
    """
    Execute graph algorithms over topology to detect structural importance,
    bottlenecks, circular deadlocks, partitions, or betweenness bridges.
    Supported: pagerank, degree_centrality, cycle_detection, connected_components,
    betweenness_centrality, closeness_centrality, community_detection, critical_dependencies.
    """
    algo = algorithm.strip().lower()
    target_graph = settings.validate_graph_name(tenant_graph)
    top_k = max(1, min(top_k, 25))

    if algo in ("pagerank", "page_rank"):
        result = run_pagerank(
            entity_kinds=entity_kinds,
            relationship_types=relationship_types,
            max_iterations=max_iterations,
            top_k=top_k,
            graph_name=target_graph,
        )
    elif algo in ("degree_centrality", "degree"):
        result = run_degree_centrality(
            entity_kinds=entity_kinds,
            top_k=top_k,
            graph_name=target_graph,
        )
    elif algo in ("cycle_detection", "cycles"):
        result = run_cycle_detection(
            relationship_types=relationship_types,
            graph_name=target_graph,
        )
    elif algo in ("connected_components", "components"):
        result = run_connected_components(graph_name=target_graph)
    elif algo in ("betweenness_centrality", "betweenness"):
        result = run_betweenness_centrality(
            top_k=top_k,
            entity_kinds=entity_kinds,
            graph_name=target_graph,
        )
    elif algo in ("closeness_centrality", "closeness"):
        result = run_closeness_centrality(
            top_k=top_k,
            entity_kinds=entity_kinds,
            graph_name=target_graph,
        )
    elif algo in ("community_detection", "communities"):
        result = run_comm_detection(
            relationship_types=relationship_types,
            max_iterations=max_iterations,
            graph_name=target_graph,
        )
    elif algo in ("critical_dependencies", "bottlenecks", "articulation_points"):
        result = detect_crit_deps(
            scope_kind=(entity_kinds[0] if entity_kinds else ""),
            relationship_types=relationship_types,
            top_k=top_k,
            graph_name=target_graph,
        )
    else:
        raise ValueError(
            f"Unsupported algorithm '{algorithm}'. Supported: pagerank, degree_centrality, cycle_detection, "
            f"connected_components, betweenness_centrality, closeness_centrality, community_detection, critical_dependencies."
        )

    result["tenant_graph"] = target_graph
    return serialize_json(result)


@mcp.tool()
def analyze_graph_impact(
    root_entity_id: str,
    direction: str = "downstream",
    max_depth: int = 4,
    tenant_graph: str = "",
) -> str:
    """
    Compute the blast radius and multi-hop consequence tree of a change, outage, or bottleneck.
    """
    target_graph = settings.validate_graph_name(tenant_graph)
    result = analyze_impact(
        root_entity_id=root_entity_id,
        direction=direction,
        max_depth=max_depth,
        graph_name=target_graph,
    )
    result["tenant_graph"] = target_graph
    return serialize_json(result)


@mcp.tool()
def retrieve_source_documents(
    entity_ids: list[str],
    limit: int = 20,
    tenant_graph: str = "",
) -> str:
    """
    Find source-document nodes, specs, and compliance records directly connected to investigated entities.
    """
    if not entity_ids:
        raise ValueError("Provide at least one entity ID")
    if len(entity_ids) > 20:
        raise ValueError("A maximum of 20 entity IDs is supported per request")

    limit = max(1, min(limit, 25))
    target_graph = settings.validate_graph_name(tenant_graph)

    query = f"""
    MATCH (doc)-[r]-(entity)
    WHERE (doc.kind = 'Document' OR 'Document' IN labels(doc) OR doc.source IS NOT NULL OR doc.source_ref IS NOT NULL)
      AND (entity.id IN $entity_ids OR entity.code IN $entity_ids OR toString(id(entity)) IN $entity_ids OR entity.name IN $entity_ids)
    RETURN DISTINCT
        coalesce(doc.id, doc.code, toString(id(doc))),
        coalesce(doc.name, doc.title, toString(id(doc))),
        coalesce(doc.source_record_id, doc.source_ref, doc.source),
        type(r),
        coalesce(entity.id, entity.code, toString(id(entity))),
        coalesce(entity.name, entity.title, toString(id(entity))),
        properties(doc)
    LIMIT {limit}
    """
    rows = execute_ro_query(query, params={"entity_ids": entity_ids}, graph_name=target_graph)

    documents = [
        {
            "id": r[0],
            "name": r[1],
            "source_record_id": r[2],
            "relationship_type": r[3],
            "linked_entity": {"id": r[4], "name": r[5]},
            "properties": r[6],
        }
        for r in rows
    ]

    return serialize_json({
        "count": len(documents),
        "documents": documents,
        "tenant_graph": target_graph,
    })


@mcp.tool()
def check_policy(
    action: str,
    target_id: str,
    assignee_id: str = "",
    params: Optional[dict[str, Any]] = None,
    tenant_graph: str = "",
) -> str:
    """
    Apply deterministic policy checks to a proposed action against explicit graph evidence.
    """
    target_graph = settings.validate_graph_name(tenant_graph)
    param_dict = dict(params or {})
    if assignee_id and "assignee_id" not in param_dict:
        param_dict["assignee_id"] = assignee_id

    result = check_action_policy(
        action=action,
        target_id=target_id,
        params=param_dict,
        graph_name=target_graph,
    )
    result["tenant_graph"] = target_graph
    return serialize_json(result)


@mcp.tool()
def simulate_action(
    action: str,
    target_id: str,
    params: Optional[dict[str, Any]] = None,
    tenant_graph: str = "",
) -> str:
    """
    Perform Counterfactual Graph Planning:
    Simulate a candidate intervention against graph topology and policies without mutating state.
    """
    target_graph = settings.validate_graph_name(tenant_graph)
    result = simulate_candidate_action(
        action=action,
        target_id=target_id,
        params=params or {},
        graph_name=target_graph,
    )
    result["tenant_graph"] = target_graph
    return serialize_json(result)


@mcp.tool()
def propose_action(
    action: str,
    target_id: str,
    rationale: str,
    evidence_ids: Optional[list[str]] = None,
    params: Optional[dict[str, Any]] = None,
    tenant_graph: str = "",
) -> str:
    """
    Formally propose a candidate action bound to graph evidence, policy checks, and simulation.
    Creates an auditable ActionProposal in the graph and issues an authorization token if approved.
    """
    target_graph = settings.validate_graph_name(tenant_graph)
    result = prop_action(
        action=action,
        target_id=target_id,
        rationale=rationale,
        evidence_ids=evidence_ids or [],
        params=params or {},
        graph_name=target_graph,
    )
    result["tenant_graph"] = target_graph
    return serialize_json(result)


@mcp.tool()
def execute_approved_action(
    proposal_id: str,
    approval_token: str,
    tenant_graph: str = "",
) -> str:
    """
    Execute a formally approved action with cryptographic token authorization,
    idempotent state mutation, and permanent audit logging in the graph.
    """
    target_graph = settings.validate_graph_name(tenant_graph)
    result = exec_approved_action(
        proposal_id=proposal_id,
        approval_token=approval_token,
        graph_name=target_graph,
    )
    result["tenant_graph"] = target_graph
    return serialize_json(result)


@mcp.tool()
def record_outcome(
    finding_id: str,
    target_entity_ids: list[str],
    summary: str,
    outcome_status: str,
    evidence_refs: Optional[list[str]] = None,
    variance_analysis: Optional[str] = None,
    tenant_graph: str = "",
) -> str:
    """
    Record durable, graph-connected organizational memory.
    """
    target_graph = settings.validate_graph_name(tenant_graph)
    result = rec_outcome(
        finding_id=finding_id,
        target_entity_ids=target_entity_ids,
        summary=summary,
        outcome_status=outcome_status,
        evidence_refs=evidence_refs or [],
        variance_analysis=variance_analysis or "",
        graph_name=target_graph,
    )
    result["tenant_graph"] = target_graph
    return serialize_json(result)


@mcp.tool()
def discover_relationship_patterns(
    entity_id: str,
    max_depth: int = 3,
    min_frequency: int = 1,
    tenant_graph: str = "",
) -> str:
    """
    Discover recurring multi-hop relationship patterns, indirect connections,
    and structural motifs (e.g. triangular reinforcements) around an entity.
    """
    res = disc_rel_patterns(
        entity_id=entity_id,
        max_depth=max_depth,
        min_frequency=min_frequency,
        tenant_graph=tenant_graph,
    )
    return serialize_json(res)


@mcp.tool()
def find_common_neighbors(
    entity_ids: list[str],
    direction: str = "both",
    limit: int = 25,
    tenant_graph: str = "",
) -> str:
    """
    Identify common dependencies, teams, resources, or services connecting 2 or more entities,
    with Jaccard similarity and Adamic-Adar specificity weighting.
    """
    res = find_com_neighbors(
        entity_ids=entity_ids,
        direction=direction,
        limit=limit,
        tenant_graph=tenant_graph,
    )
    return serialize_json(res)


@mcp.tool()
def find_alternative_paths(
    source_id: str,
    target_id: str,
    max_depth: int = 6,
    max_paths: int = 5,
    relationship_types: Optional[list[str]] = None,
    tenant_graph: str = "",
) -> str:
    """
    Discover multiple independent and alternative paths between two entities,
    evaluating path redundancy, node-disjoint independence, and intermediate bottlenecks.
    """
    res = find_alt_paths(
        source_id=source_id,
        target_id=target_id,
        max_depth=max_depth,
        max_paths=max_paths,
        relationship_types=relationship_types,
        tenant_graph=tenant_graph,
    )
    return serialize_json(res)


@mcp.tool()
def detect_critical_dependencies(
    scope_kind: str = "",
    relationship_types: Optional[list[str]] = None,
    top_k: int = 10,
    tenant_graph: str = "",
) -> str:
    """
    Detect articulation points (cut vertices) and single points of failure whose removal
    or failure fragments the graph into disconnected components.
    """
    target_graph = settings.validate_graph_name(tenant_graph)
    res = detect_crit_deps(
        scope_kind=scope_kind,
        relationship_types=relationship_types,
        top_k=top_k,
        graph_name=target_graph,
    )
    res["tenant_graph"] = target_graph
    return serialize_json(res)


@mcp.tool()
def detect_communities(
    relationship_types: Optional[list[str]] = None,
    max_iterations: int = 20,
    min_community_size: int = 2,
    tenant_graph: str = "",
) -> str:
    """
    Discover tightly-knit entity clusters and functional modules using asynchronous
    Label Propagation Algorithm (LPA), highlighting inter-community bridge edges.
    """
    target_graph = settings.validate_graph_name(tenant_graph)
    res = run_comm_detection(
        relationship_types=relationship_types,
        max_iterations=max_iterations,
        min_community_size=min_community_size,
        graph_name=target_graph,
    )
    res["tenant_graph"] = target_graph
    return serialize_json(res)


@mcp.tool()
def detect_graph_anomalies(
    anomaly_types: Optional[list[str]] = None,
    tenant_graph: str = "",
) -> str:
    """
    Identify isolated/orphaned nodes, potential duplicate entities, extreme degree spikes,
    and unverified relationships lacking source records.
    """
    res = detect_anomalies(
        anomaly_types=anomaly_types,
        tenant_graph=tenant_graph,
    )
    return serialize_json(res)


@mcp.tool()
def analyze_reachability(
    start_entity_id: str,
    target_entity_ids: Optional[list[str]] = None,
    direction: str = "downstream",
    max_depth: int = 5,
    relationship_types: Optional[list[str]] = None,
    target_kinds: Optional[list[str]] = None,
    tenant_graph: str = "",
) -> str:
    """
    Determine which entities and asset types are reachable from a starting entity under
    specified direction, depth, relationship, and target-kind constraints.
    """
    res = analyze_reach(
        start_entity_id=start_entity_id,
        target_entity_ids=target_entity_ids,
        direction=direction,
        max_depth=max_depth,
        relationship_types=relationship_types,
        target_kinds=target_kinds,
        tenant_graph=tenant_graph,
    )
    return serialize_json(res)


@mcp.tool()
def compare_connectivity(
    source_a_id: str,
    source_b_id: str,
    target_id: str = "",
    tenant_graph: str = "",
) -> str:
    """
    Compare how two entities or graph regions are structured, contrasting degrees,
    shared vs unique neighbors, and proximity to an optional target.
    """
    res = comp_connectivity(
        source_a_id=source_a_id,
        source_b_id=source_b_id,
        target_id=target_id,
        tenant_graph=tenant_graph,
    )
    return serialize_json(res)


@mcp.tool()
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
) -> str:
    """
    Search graph entities using multi-faceted criteria (kinds, statuses, property values,
    relationship connectivity) with pagination support (offset, limit, has_more).
    """
    res = search_ents_advanced(
        query=query,
        kinds=kinds,
        statuses=statuses,
        property_filters=property_filters,
        connected_to=connected_to,
        has_relationship=has_relationship,
        limit=limit,
        offset=offset,
        tenant_graph=tenant_graph,
    )
    return serialize_json(res)


@mcp.tool()
def compare_entities(
    entity_ids: list[str],
    include_relationships: bool = True,
    tenant_graph: str = "",
) -> str:
    """
    Perform a side-by-side comparison of 2 or more entities, contrasting their properties,
    incoming/outgoing connections, dependencies, and evidence provenance.
    """
    res = comp_entities(
        entity_ids=entity_ids,
        include_relationships=include_relationships,
        tenant_graph=tenant_graph,
    )
    return serialize_json(res)


@mcp.tool()
def investigate_entity_cluster(
    entity_ids: list[str],
    max_depth: int = 2,
    max_neighbors_per_entity: int = 15,
    tenant_graph: str = "",
) -> str:
    """
    Explore multiple entities within a single bounded operation, discovering mutual
    interconnections, shared dependencies, bridging nodes, and aggregated risks.
    """
    res = inv_cluster(
        entity_ids=entity_ids,
        max_depth=max_depth,
        max_neighbors_per_entity=max_neighbors_per_entity,
        tenant_graph=tenant_graph,
    )
    return serialize_json(res)


@mcp.tool()
def extract_investigation_subgraph(
    focal_entity_ids: list[str],
    max_depth: int = 2,
    max_nodes: int = 50,
    relationship_types: Optional[list[str]] = None,
    tenant_graph: str = "",
) -> str:
    """
    Extract a compact, relevant, bounded subgraph around focal entities
    tailored for investigation context, visual inspection, and agent reasoning.
    """
    res = extract_subgraph(
        focal_entity_ids=focal_entity_ids,
        max_depth=max_depth,
        max_nodes=max_nodes,
        relationship_types=relationship_types,
        tenant_graph=tenant_graph,
    )
    return serialize_json(res)


@mcp.tool()
def compare_evidence_paths(
    source_id: str,
    target_id: str,
    candidate_paths_limit: int = 4,
    max_depth: int = 6,
    tenant_graph: str = "",
) -> str:
    """
    Compare multiple candidate evidence paths between two entities, ranking them by
    hop distance, cumulative confidence score, verification rate, and freshness.
    """
    res = comp_evidence_paths(
        source_id=source_id,
        target_id=target_id,
        candidate_paths_limit=candidate_paths_limit,
        max_depth=max_depth,
        tenant_graph=tenant_graph,
    )
    return serialize_json(res)


@mcp.tool()
def batch_get_entities(
    entity_ids: list[str],
    include_relationships: bool = False,
    tenant_graph: str = "",
) -> str:
    """
    Retrieve multiple entities in a single efficient batch query (up to 50 entities).
    """
    res = batch_get_ents(
        entity_ids=entity_ids,
        include_relationships=include_relationships,
        tenant_graph=tenant_graph,
    )
    return serialize_json(res)


@mcp.tool()
def generate_investigation_summary(
    investigation_title: str,
    entity_ids: list[str],
    tenant_graph: str = "",
) -> str:
    """
    Synthesize graph investigation findings, distinguishing observed facts from
    derived connections and unresolved data gaps.
    """
    res = gen_inv_summary(
        investigation_title=investigation_title,
        entity_ids=entity_ids,
        tenant_graph=tenant_graph,
    )
    return serialize_json(res)


@mcp.tool()
def discover_graph_schema(
    sample_size: int = 100,
    refresh_cache: bool = False,
    tenant_graph: str = "",
) -> str:
    """
    Safely discover graph schema, structural topology, entity kinds, relationship directions,
    property catalogs, and schema anomalies across any graph domain without hard-coded ontology assumptions.
    """
    res = disc_schema(
        sample_size=sample_size,
        refresh_cache=refresh_cache,
        tenant_graph=tenant_graph,
    )
    return serialize_json(res)


@mcp.tool()
def evaluate_evidence_quality(
    entity_id: str = "",
    max_depth: int = 2,
    stale_days_threshold: int = 30,
    tenant_graph: str = "",
) -> str:
    """
    Evaluate evidence freshness, provenance verification rates, confidence distribution,
    and missing evidence records across the graph or an entity neighborhood.
    """
    res = eval_evidence_quality(
        entity_id=entity_id,
        max_depth=max_depth,
        stale_days_threshold=stale_days_threshold,
        tenant_graph=tenant_graph,
    )
    return serialize_json(res)


@mcp.tool()
def detect_conflicting_evidence(
    scope_entity_ids: Optional[list[str]] = None,
    tenant_graph: str = "",
) -> str:
    """
    Detect conflicting evidence, contradictory relationship states,
    and mutually exclusive claims across entities.
    """
    res = detect_conflicts(
        scope_entity_ids=scope_entity_ids,
        tenant_graph=tenant_graph,
    )
    return serialize_json(res)


@mcp.tool()
def inspect_temporal_graph(
    entity_id: str,
    as_of_timestamp: Optional[str] = None,
    time_window_days: Optional[int] = None,
    tenant_graph: str = "",
) -> str:
    """
    Inspect the temporal evolution of relationships and events connected to an entity,
    identifying historical milestones, recent changes, and observation timelines.
    """
    res = insp_temporal_graph(
        entity_id=entity_id,
        as_of_timestamp=as_of_timestamp,
        time_window_days=time_window_days,
        tenant_graph=tenant_graph,
    )
    return serialize_json(res)


@mcp.tool()
def assess_change_risk_and_impact(
    proposed_change_type: str,
    target_entity_id: str,
    parameters: Optional[dict[str, Any]] = None,
    max_depth: int = 4,
    tenant_graph: str = "",
) -> str:
    """
    Perform deep graph-guided impact and risk analysis for proposed operational or architectural changes,
    identifying critical cascades, alternative fallback paths, isolated components, and unresolved prerequisites.
    """
    res = assess_change_impact(
        proposed_change_type=proposed_change_type,
        target_entity_id=target_entity_id,
        parameters=parameters,
        max_depth=max_depth,
        tenant_graph=tenant_graph,
    )
    return serialize_json(res)


@mcp.tool()
def evaluate_candidate_actions(
    candidate_actions: list[dict[str, Any]],
    target_entity_id: str = "",
    tenant_graph: str = "",
) -> str:
    """
    Compare multiple candidate actions side-by-side against graph evidence and policy constraints,
    producing an explainable comparison matrix and rank-ordered recommendation.
    """
    res = eval_candidate_actions(
        candidate_actions=candidate_actions,
        target_entity_id=target_entity_id,
        tenant_graph=tenant_graph,
    )
    return serialize_json(res)


@mcp.tool()
def query_decision_memory(
    query: str = "",
    entity_id: str = "",
    status: str = "",
    limit: int = 20,
    tenant_graph: str = "",
) -> str:
    """
    Retrieve historical organizational decisions, action proposals, executed outcomes,
    and investigation findings with full provenance and status tracking.
    """
    target_graph = settings.validate_graph_name(tenant_graph)
    res = query_dec_memory(
        query=query,
        entity_id=entity_id,
        status=status,
        limit=limit,
        graph_name=target_graph,
    )
    return serialize_json(res)


@mcp.tool()
def record_investigation_finding(
    title: str,
    objective: str,
    key_findings: list[str],
    supporting_entity_ids: list[str],
    evidence_path_ids: Optional[list[str]] = None,
    confidence: str = "HIGH",
    tenant_graph: str = "",
) -> str:
    """
    Record a durable, graph-connected investigation finding with links to supporting entities and evidence.
    """
    target_graph = settings.validate_graph_name(tenant_graph)
    res = rec_inv_finding(
        title=title,
        objective=objective,
        key_findings=key_findings,
        supporting_entity_ids=supporting_entity_ids,
        evidence_path_ids=evidence_path_ids,
        confidence=confidence,
        graph_name=target_graph,
    )
    return serialize_json(res)


@mcp.tool()
def supersede_finding(
    finding_id: str,
    reason: str,
    superseding_finding_id: str = "",
    new_evidence_refs: Optional[list[str]] = None,
    tenant_graph: str = "",
) -> str:
    """
    Challenge or update a historical finding with newer evidence, marking it SUPERSEDED
    while preserving permanent audit history.
    """
    target_graph = settings.validate_graph_name(tenant_graph)
    res = sup_finding(
        finding_id=finding_id,
        reason=reason,
        superseding_finding_id=superseding_finding_id,
        new_evidence_refs=new_evidence_refs,
        graph_name=target_graph,
    )
    return serialize_json(res)

@mcp.tool()
def run_read_only_cypher_query(
    query: str,
    params: Optional[dict[str, Any]] = None,
    limit: int = 50,
    tenant_graph: str = "",
) -> str:
    """
    Execute a safe, validated read-only Cypher query against the connected graph schema.
    Enforces strict read-only execution: rejects CREATE, MERGE, SET, DELETE, REMOVE, DROP, ALTER.
    """
    query = query.strip()
    if not query:
        raise ValueError("query must not be empty")

    forbidden_pattern = re.compile(
        r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DROP|ALTER|CALL\s+dbms)\b",
        re.IGNORECASE,
    )
    if forbidden_pattern.search(query):
        raise ValueError("Mutation or administrative Cypher keywords are forbidden in read-only queries.")

    limit = max(1, min(limit, 100))
    if "LIMIT" not in query.upper():
        query = f"{query}\nLIMIT {limit}"

    target_graph = settings.validate_graph_name(tenant_graph)
    rows = execute_ro_query(query, params=params or {}, graph_name=target_graph)

    return serialize_json({
        "query": query,
        "count": len(rows),
        "results": rows,
        "tenant_graph": target_graph,
    })


if __name__ == "__main__":
    mcp.run()
