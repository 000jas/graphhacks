from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

from db import execute_ro_query


def run_pagerank(
    entity_kinds: Optional[list[str]] = None,
    relationship_types: Optional[list[str]] = None,
    damping_factor: float = 0.85,
    max_iterations: int = 25,
    top_k: int = 10,
    graph_name: Optional[str] = None,
) -> dict[str, Any]:
    """Calculate PageRank centrality over graph topology."""
    kinds_filter = ""
    if entity_kinds:
        kinds_filter = "WHERE source.kind IN $kinds AND target.kind IN $kinds"

    rel_filter = ""
    if relationship_types:
        rel_clause = "WHERE" if not kinds_filter else "AND"
        rel_filter = f"{rel_clause} type(r) IN $rels"

    query = f"""
    MATCH (source:Entity)-[r]->(target:Entity)
    {kinds_filter}
    {rel_filter}
    RETURN source.id, source.name, source.kind, target.id, target.name, target.kind
    """
    params: dict[str, Any] = {}
    if entity_kinds:
        params["kinds"] = entity_kinds
    if relationship_types:
        params["rels"] = relationship_types

    rows = execute_ro_query(query, params=params, graph_name=graph_name)

    nodes: dict[str, dict[str, str]] = {}
    out_edges: dict[str, set[str]] = defaultdict(set)
    in_edges: dict[str, set[str]] = defaultdict(set)

    for s_id, s_name, s_kind, t_id, t_name, t_kind in rows:
        nodes[s_id] = {"id": s_id, "name": s_name, "kind": s_kind}
        nodes[t_id] = {"id": t_id, "name": t_name, "kind": t_kind}
        out_edges[s_id].add(t_id)
        in_edges[t_id].add(s_id)

    n_nodes = len(nodes)
    if n_nodes == 0:
        return {
            "algorithm": "PageRank",
            "count": 0,
            "ranked_entities": [],
            "interpretation": "No matching entities or relationships found within the specified filters.",
            "limitations": "Graph was empty for the provided criteria.",
        }

    ranks = {node_id: 1.0 / n_nodes for node_id in nodes}

    for _ in range(max_iterations):
        new_ranks: dict[str, float] = {}
        dangling_sum = sum(ranks[node_id] for node_id in nodes if not out_edges[node_id])

        for node_id in nodes:
            incoming_sum = sum(ranks[src] / len(out_edges[src]) for src in in_edges[node_id])
            new_ranks[node_id] = (
                (1.0 - damping_factor) / n_nodes
                + damping_factor * (incoming_sum + dangling_sum / n_nodes)
            )
        ranks = new_ranks

    sorted_ranks = sorted(ranks.items(), key=lambda item: item[1], reverse=True)[:top_k]

    results = []
    for rank_idx, (node_id, score) in enumerate(sorted_ranks, start=1):
        info = nodes[node_id]
        results.append({
            "rank": rank_idx,
            "id": node_id,
            "name": info["name"],
            "kind": info["kind"],
            "score": round(score, 6),
            "in_degree": len(in_edges[node_id]),
            "out_degree": len(out_edges[node_id]),
        })

    return {
        "algorithm": "PageRank",
        "parameters": {
            "damping_factor": damping_factor,
            "iterations": max_iterations,
            "entity_kinds": entity_kinds or "all",
            "relationship_types": relationship_types or "all",
        },
        "count": len(results),
        "ranked_entities": results,
        "interpretation": (
            "Identifies foundational entities with highest structural authority and inbound transitive dependencies. "
            "High PageRank signifies a core service, critical team, or pervasive policy whose degradation impacts wide areas."
        ),
        "limitations": (
            "Treats all relationship types with equal weight unless filtered. "
            "Directionality matters: incoming edges increase target authority."
        ),
    }


def run_degree_centrality(
    entity_kinds: Optional[list[str]] = None,
    top_k: int = 10,
    graph_name: Optional[str] = None,
) -> dict[str, Any]:
    """Calculate in-degree, out-degree, and total degree centrality."""
    kind_clause = "WHERE n.kind IN $kinds" if entity_kinds else ""
    params = {"kinds": entity_kinds} if entity_kinds else None

    in_query = f"""
    MATCH (n:Entity)
    {kind_clause}
    OPTIONAL MATCH ()-[r_in]->(n)
    RETURN n.id, n.name, n.kind, count(r_in) AS in_degree
    ORDER BY in_degree DESC
    """
    out_query = f"""
    MATCH (n:Entity)
    {kind_clause}
    OPTIONAL MATCH (n)-[r_out]->()
    RETURN n.id, n.name, n.kind, count(r_out) AS out_degree
    ORDER BY out_degree DESC
    """

    in_rows = execute_ro_query(in_query, params=params, graph_name=graph_name)
    out_rows = execute_ro_query(out_query, params=params, graph_name=graph_name)

    in_map = {row[0]: (row[1], row[2], row[3]) for row in in_rows}
    out_map = {row[0]: row[3] for row in out_rows}

    combined = []
    for node_id, (name, kind, in_deg) in in_map.items():
        out_deg = out_map.get(node_id, 0)
        total = in_deg + out_deg
        combined.append({
            "id": node_id,
            "name": name,
            "kind": kind,
            "total_degree": total,
            "in_degree": in_deg,
            "out_degree": out_deg,
        })

    combined.sort(key=lambda x: x["total_degree"], reverse=True)
    top_results = combined[:top_k]

    return {
        "algorithm": "DegreeCentrality",
        "parameters": {"entity_kinds": entity_kinds or "all", "top_k": top_k},
        "count": len(top_results),
        "ranked_entities": top_results,
        "interpretation": (
            "Measures immediate connectivity. High in-degree reflects heavily depended-on entities "
            "(potential single points of failure). High out-degree reflects orchestrators or coordinators "
            "with many downstream obligations."
        ),
        "limitations": "Local metric only; does not capture multi-hop transitive dependencies.",
    }


def run_cycle_detection(
    relationship_types: Optional[list[str]] = None,
    graph_name: Optional[str] = None,
) -> dict[str, Any]:
    """Detect circular dependencies or blocking loops in directed graph structures."""
    rel_filter = ""
    params: dict[str, Any] = {}
    if relationship_types:
        rel_filter = "WHERE type(r) IN $rels"
        params["rels"] = relationship_types

    query = f"""
    MATCH (source:Entity)-[r]->(target:Entity)
    {rel_filter}
    RETURN source.id, source.name, type(r), target.id, target.name
    """
    rows = execute_ro_query(query, params=params, graph_name=graph_name)

    adj: dict[str, list[tuple[str, str]]] = defaultdict(list)
    names: dict[str, str] = {}

    for s_id, s_name, r_type, t_id, t_name in rows:
        adj[s_id].append((t_id, r_type))
        names[s_id] = s_name
        names[t_id] = t_name

    cycles: list[list[dict[str, str]]] = []
    visited: set[str] = set()
    rec_stack: list[str] = []
    rec_stack_set: set[str] = set()

    def dfs(u: str) -> None:
        visited.add(u)
        rec_stack.append(u)
        rec_stack_set.add(u)

        for v, rel in adj[u]:
            if v not in visited:
                dfs(v)
            elif v in rec_stack_set:
                cycle_slice = rec_stack[rec_stack.index(v):] + [v]
                cycle_repr = [
                    {"id": node_id, "name": names.get(node_id, node_id)}
                    for node_id in cycle_slice
                ]
                cycles.append(cycle_repr)

        rec_stack.pop()
        rec_stack_set.remove(u)

    for node in list(adj.keys()):
        if node not in visited:
            dfs(node)

    return {
        "algorithm": "CycleDetection",
        "cycles_found": len(cycles),
        "cycles": cycles[:10],
        "interpretation": (
            "Detects recursive deadlocks or circular dependencies. "
            "In engineering or task management, circular dependencies prevent orderly execution and release."
        ),
        "limitations": "Reports up to 10 distinct elementary cycles.",
    }


def run_connected_components(graph_name: Optional[str] = None) -> dict[str, Any]:
    """Compute weakly connected components to identify organizational and architectural partitions."""
    query = """
    MATCH (source:Entity)-[r]->(target:Entity)
    RETURN source.id, source.name, source.kind, target.id, target.name, target.kind
    """
    rows = execute_ro_query(query, graph_name=graph_name)

    parent: dict[str, str] = {}
    nodes: dict[str, dict[str, str]] = {}

    def find(i: str) -> str:
        if parent[i] == i:
            return i
        parent[i] = find(parent[i])
        return parent[i]

    def union(i: str, j: str) -> None:
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            parent[root_i] = root_j

    for s_id, s_name, s_kind, t_id, t_name, t_kind in rows:
        nodes[s_id] = {"id": s_id, "name": s_name, "kind": s_kind}
        nodes[t_id] = {"id": t_id, "name": t_name, "kind": t_kind}
        if s_id not in parent:
            parent[s_id] = s_id
        if t_id not in parent:
            parent[t_id] = t_id
        union(s_id, t_id)

    components: dict[str, list[dict[str, str]]] = defaultdict(list)
    for node_id, info in nodes.items():
        root = find(node_id)
        components[root].append(info)

    sorted_components = sorted(
        [{"component_root": root, "size": len(members), "sample_members": members[:5]} for root, members in components.items()],
        key=lambda c: c["size"],
        reverse=True,
    )

    return {
        "algorithm": "ConnectedComponents",
        "total_components": len(sorted_components),
        "components": sorted_components,
        "interpretation": (
            "Partitions graph into disconnected clusters. Isolated components indicate decoupled domains "
            "or data silos that do not share direct relationships with the main graph."
        ),
        "limitations": "Evaluates weak connectivity (disregarding edge directionality).",
    }
