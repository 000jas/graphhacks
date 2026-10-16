from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

# Ensure mcp_server directory is in sys.path
SERVER_DIR = Path(__file__).resolve().parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from mcp.server import MCPServer

from algorithms import (
    run_connected_components,
    run_cycle_detection,
    run_degree_centrality,
    run_pagerank,
)
from config import settings
from counterfactual import simulate_candidate_action
from db import execute_ro_query
from decision_memory import (
    execute_approved_action as exec_approved_action,
    propose_action as prop_action,
    record_outcome as rec_outcome,
)
from impact import analyze_graph_impact as analyze_impact
from models import serialize_json
from policy import check_action_policy

mcp = MCPServer(
    name="GraphOS",
    instructions=(
        "GraphOS Evidence-Bound MCP Server: Exposes structured graph intelligence, multi-hop evidence paths, "
        "graph algorithms, blast radius analysis, counterfactual simulations, policy enforcement, "
        "and durable organizational memory over a cloud-hosted FalkorDB instance."
    ),
)

ALLOWED_RELATIONSHIPS = {
    "HAS_RELEASE", "HAS_TEAM", "DEPLOYS", "TARGETS_ENV",
    "BLOCKED_BY", "REQUIRES", "GOVERNED_BY", "IMPLEMENTED_IN",
    "DEPENDS_ON", "DEPLOYED_TO", "HAS_PULL_REQUEST", "CONTAINS",
    "MODIFIES", "INTRODUCES_DEPENDENCY", "AUTHORED_BY",
    "ASSOCIATED_WITH", "CHECKED_BY", "DOCUMENTED_IN",
    "ASSIGNED_TO", "OWNED_BY", "HAS_EVENT", "TRIGGERS",
    "EXPLAINS", "APPLIES_TO", "HAS_MEMBER", "PART_OF",
    "IMPACTS", "TRACED_TO", "RUNS_ON", "VALIDATES", "USED_BY",
    "COVERS",
}


def entity_row(row: list[Any]) -> dict[str, Any]:
    return {
        "id": row[0],
        "name": row[1],
        "kind": row[2],
        "status": row[3],
        "source_ref": row[4],
    }


# TOOL 1: search_connected_entities
@mcp.tool()
def search_connected_entities(
    query: str,
    limit: int = 10,
    kind: str = "",
    tenant_graph: str = "",
) -> str:
    """
    Search graph entities by partial name, identifier, or classification.
    """
    query = query.strip()
    if not query:
        raise ValueError("query must not be empty")
    if len(query) > 200:
        raise ValueError("query must be at most 200 characters")

    limit = max(1, min(limit, 25))
    target_graph = settings.validate_graph_name(tenant_graph)

    kind_filter = ""
    params: dict[str, Any] = {"query": query}
    if kind:
        kind_filter = "AND n.kind = $kind"
        params["kind"] = kind

    cypher = f"""
    MATCH (n:Entity)
    WHERE (toLower(n.name) CONTAINS toLower($query)
       OR toLower(n.id) CONTAINS toLower($query))
       {kind_filter}
    RETURN n.id, n.name, n.kind, n.status, n.source_ref
    ORDER BY n.name
    LIMIT {limit}
    """
    rows = execute_ro_query(cypher, params=params, graph_name=target_graph)

    return serialize_json({
        "query": query,
        "count": len(rows),
        "entities": [entity_row(row) for row in rows],
        "tenant_graph": target_graph,
    })


# TOOL 2: get_entity_profile
@mcp.tool()
def get_entity_profile(
    entity_id: str,
    tenant_graph: str = "",
) -> str:
    """
    Retrieve comprehensive intelligence for a specific entity including properties,
    source provenance references, and both incoming and outgoing relationships.
    """
    entity_id = entity_id.strip()
    if not entity_id:
        raise ValueError("entity_id must not be empty")

    target_graph = settings.validate_graph_name(tenant_graph)

    rows = execute_ro_query(
        """
        MATCH (n:Entity {id: $entity_id})
        RETURN n.id, n.name, n.kind, labels(n), properties(n)
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

    outgoing = execute_ro_query(
        """
        MATCH (n:Entity {id: $entity_id})-[r]->(other:Entity)
        RETURN type(r), other.id, other.name, other.kind, properties(r)
        LIMIT 50
        """,
        params={"entity_id": entity_id},
        graph_name=target_graph,
    )

    incoming = execute_ro_query(
        """
        MATCH (other:Entity)-[r]->(n:Entity {id: $entity_id})
        RETURN type(r), other.id, other.name, other.kind, properties(r)
        LIMIT 50
        """,
        params={"entity_id": entity_id},
        graph_name=target_graph,
    )

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
                "target": {"id": r[1], "name": r[2], "kind": r[3]},
                "evidence": r[4],
            }
            for r in outgoing
        ],
        "incoming_relationships": [
            {
                "type": r[0],
                "source": {"id": r[1], "name": r[2], "kind": r[3]},
                "evidence": r[4],
            }
            for r in incoming
        ],
        "tenant_graph": target_graph,
    })


# TOOL 3: traverse_relationships
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
    """
    entity_id = entity_id.strip()
    if not entity_id:
        raise ValueError("entity_id must not be empty")

    if not 1 <= depth <= 4:
        raise ValueError("depth must be between 1 and 4")

    limit = max(1, min(limit, 50))
    target_graph = settings.validate_graph_name(tenant_graph)

    rel_types = relationship_types or []
    unknown = set(rel_types) - ALLOWED_RELATIONSHIPS
    if unknown:
        raise ValueError(f"Unsupported relationship types: {sorted(unknown)}")

    path_filter = ""
    params: dict[str, Any] = {"entity_id": entity_id}

    if rel_types:
        path_filter = """
          AND all(rel IN relationships(p)
                  WHERE type(rel) IN $relationship_types)
        """
        params["relationship_types"] = rel_types

    query = f"""
    MATCH p = (start:Entity {{id: $entity_id}})
              -[*1..{depth}]-(neighbor:Entity)
    WHERE neighbor.id <> start.id
    {path_filter}
    RETURN
        neighbor.id,
        neighbor.name,
        neighbor.kind,
        length(p),
        [node IN nodes(p) |
            {{id: node.id, name: node.name, kind: node.kind}}]
            AS path_nodes,
        [rel IN relationships(p) |
            {{
                type: type(rel),
                source_record_id: rel.source_record_id,
                observed_at: rel.observed_at,
                confidence: rel.confidence
            }}]
            AS path_edges
    ORDER BY length(p), neighbor.name
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
        "start_entity_id": entity_id,
        "depth_limit": depth,
        "count": len(paths),
        "paths": paths,
        "tenant_graph": target_graph,
    })


# TOOL 4: find_shortest_evidence_path
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
    MATCH p = (source:Entity {{id: $source_id}})
              -[*1..{max_depth}]-
              (target:Entity {{id: $target_id}})
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


# TOOL 5: run_graph_algorithm
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
    Execute standard graph algorithms over graph topology to detect structural importance,
    bottlenecks, circular deadlocks, or partitions.
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
    else:
        raise ValueError(
            f"Unsupported algorithm '{algorithm}'. Supported: pagerank, degree_centrality, cycle_detection, connected_components."
        )

    result["tenant_graph"] = target_graph
    return serialize_json(result)


# TOOL 6: analyze_graph_impact
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


# TOOL 7: retrieve_source_documents
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
    MATCH (doc:Entity)-[r]-(entity:Entity)
    WHERE doc.kind = 'Document'
      AND entity.id IN $entity_ids
    RETURN DISTINCT
        doc.id, doc.name, doc.source_record_id,
        type(r), entity.id, entity.name,
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


# TOOL 8: check_policy
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


# TOOL 9: simulate_action
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


# TOOL 10: propose_action
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


# TOOL 11: execute_approved_action
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


# TOOL 12: record_outcome
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


if __name__ == "__main__":
    mcp.run()
