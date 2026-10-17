from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

try:
    from mcp_server.db import execute_ro_query
except ImportError:
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
        "cycles": [
            {
                "cycle_index": idx + 1,
                "length": len(c),
                "entities": c,
                "recommended_loop_breaker": f"Decouple direct dependency between '{c[-2]['name']}' and '{c[-1]['name']}' to eliminate circular lock.",
            }
            for idx, c in enumerate(cycles[:10])
        ],
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


def run_betweenness_centrality(
    top_k: int = 10,
    entity_kinds: Optional[list[str]] = None,
    graph_name: Optional[str] = None,
) -> dict[str, Any]:
    """
    Calculate Betweenness Centrality using Brandes algorithm to identify gatekeeper entities
    and communication bridges across graph partitions.
    """
    kinds_filter = ""
    params: dict[str, Any] = {}
    if entity_kinds:
        kinds_filter = "WHERE source.kind IN $kinds AND target.kind IN $kinds"
        params["kinds"] = entity_kinds

    query = f"""
    MATCH (source:Entity)-[r]->(target:Entity)
    {kinds_filter}
    RETURN source.id, source.name, source.kind, target.id, target.name, target.kind
    """
    rows = execute_ro_query(query, params=params, graph_name=graph_name)

    nodes: dict[str, dict[str, str]] = {}
    adj: dict[str, set[str]] = defaultdict(set)

    for s_id, s_name, s_kind, t_id, t_name, t_kind in rows:
        nodes[s_id] = {"id": s_id, "name": s_name, "kind": s_kind}
        nodes[t_id] = {"id": t_id, "name": t_name, "kind": t_kind}
        adj[s_id].add(t_id)
        adj[t_id].add(s_id)

    n = len(nodes)
    if n <= 2:
        return {
            "algorithm": "BetweennessCentrality",
            "count": 0,
            "ranked_entities": [],
            "interpretation": "Insufficient nodes for betweenness centrality calculation.",
            "limitations": "Requires at least 3 connected nodes.",
        }

    cb: dict[str, float] = {node_id: 0.0 for node_id in nodes}

    for s in nodes:
        stack: list[str] = []
        p: dict[str, list[str]] = {w: [] for w in nodes}
        sigma: dict[str, int] = {w: 0 for w in nodes}
        sigma[s] = 1
        d: dict[str, int] = {w: -1 for w in nodes}
        d[s] = 0

        queue: list[str] = [s]
        head = 0
        while head < len(queue):
            v = queue[head]
            head += 1
            stack.append(v)

            for w in adj[v]:
                if d[w] < 0:
                    queue.append(w)
                    d[w] = d[v] + 1
                if d[w] == d[v] + 1:
                    sigma[w] += sigma[v]
                    p[w].append(v)

        delta: dict[str, float] = {w: 0.0 for w in nodes}
        while stack:
            w = stack.pop()
            for v in p[w]:
                if sigma[w] > 0:
                    delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
            if w != s:
                cb[w] += delta[w]

    norm_factor = 2.0 / ((n - 1) * (n - 2)) if n > 2 else 1.0
    sorted_cb = sorted(cb.items(), key=lambda x: x[1], reverse=True)[:top_k]

    results = []
    for rank_idx, (node_id, score) in enumerate(sorted_cb, start=1):
        info = nodes[node_id]
        normalized_score = round((score / 2.0) * norm_factor, 6)
        results.append({
            "rank": rank_idx,
            "id": node_id,
            "name": info["name"],
            "kind": info["kind"],
            "betweenness_score": normalized_score,
            "degree": len(adj[node_id]),
        })

    return {
        "algorithm": "BetweennessCentrality",
        "parameters": {"top_k": top_k, "entity_kinds": entity_kinds or "all"},
        "count": len(results),
        "ranked_entities": results,
        "interpretation": (
            "Measures how often an entity falls on the shortest paths between other entities. "
            "High betweenness indicates critical bridges, gatekeepers, and coordination hubs that control graph communication."
        ),
        "limitations": "Computed on undirected topology; reflects topological bridging rather than directional flow.",
    }


def run_closeness_centrality(
    top_k: int = 10,
    entity_kinds: Optional[list[str]] = None,
    graph_name: Optional[str] = None,
) -> dict[str, Any]:
    """Calculate Closeness Centrality to identify entities with shortest transitive distance to all others."""
    kinds_filter = ""
    params: dict[str, Any] = {}
    if entity_kinds:
        kinds_filter = "WHERE source.kind IN $kinds AND target.kind IN $kinds"
        params["kinds"] = entity_kinds

    query = f"""
    MATCH (source:Entity)-[r]->(target:Entity)
    {kinds_filter}
    RETURN source.id, source.name, source.kind, target.id, target.name, target.kind
    """
    rows = execute_ro_query(query, params=params, graph_name=graph_name)

    nodes: dict[str, dict[str, str]] = {}
    adj: dict[str, set[str]] = defaultdict(set)

    for s_id, s_name, s_kind, t_id, t_name, t_kind in rows:
        nodes[s_id] = {"id": s_id, "name": s_name, "kind": s_kind}
        nodes[t_id] = {"id": t_id, "name": t_name, "kind": t_kind}
        adj[s_id].add(t_id)
        adj[t_id].add(s_id)

    n = len(nodes)
    if n <= 1:
        return {
            "algorithm": "ClosenessCentrality",
            "count": 0,
            "ranked_entities": [],
            "interpretation": "Insufficient nodes for closeness calculation.",
            "limitations": "Requires at least 2 connected nodes.",
        }

    closeness_scores: dict[str, float] = {}

    for s in nodes:
        visited = {s: 0}
        queue = [s]
        head = 0
        total_dist = 0
        reachable_count = 0

        while head < len(queue):
            curr = queue[head]
            head += 1
            curr_dist = visited[curr]

            for neighbor in adj[curr]:
                if neighbor not in visited:
                    visited[neighbor] = curr_dist + 1
                    total_dist += curr_dist + 1
                    reachable_count += 1
                    queue.append(neighbor)

        if total_dist > 0 and reachable_count > 0:
            score = (reachable_count / total_dist) * (reachable_count / (n - 1))
        else:
            score = 0.0
        closeness_scores[s] = round(score, 6)

    sorted_scores = sorted(closeness_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    results = []
    for rank_idx, (node_id, score) in enumerate(sorted_scores, start=1):
        info = nodes[node_id]
        results.append({
            "rank": rank_idx,
            "id": node_id,
            "name": info["name"],
            "kind": info["kind"],
            "closeness_score": score,
            "degree": len(adj[node_id]),
        })

    return {
        "algorithm": "ClosenessCentrality",
        "parameters": {"top_k": top_k, "entity_kinds": entity_kinds or "all"},
        "count": len(results),
        "ranked_entities": results,
        "interpretation": (
            "Measures how quickly an entity can reach all other nodes in the network. "
            "High closeness entities can disseminate changes, policies, or notifications with minimal hops."
        ),
        "limitations": "Normalized using Wasserman & Faust to handle graphs with multiple disconnected components.",
    }


def run_community_detection(
    relationship_types: Optional[list[str]] = None,
    max_iterations: int = 20,
    min_community_size: int = 2,
    graph_name: Optional[str] = None,
) -> dict[str, Any]:
    """
    Detect communities and clusters using asynchronous Label Propagation Algorithm (LPA),
    identifying tightly-coupled groups and cross-community bridge relationships.
    """
    rel_filter = ""
    params: dict[str, Any] = {}
    if relationship_types:
        rel_filter = "WHERE type(r) IN $rels"
        params["rels"] = relationship_types

    query = f"""
    MATCH (source:Entity)-[r]->(target:Entity)
    {rel_filter}
    RETURN source.id, source.name, source.kind, target.id, target.name, target.kind, type(r)
    """
    rows = execute_ro_query(query, params=params, graph_name=graph_name)

    nodes: dict[str, dict[str, str]] = {}
    adj: dict[str, set[str]] = defaultdict(set)
    edges_list: list[tuple[str, str, str]] = []

    for s_id, s_name, s_kind, t_id, t_name, t_kind, r_type in rows:
        nodes[s_id] = {"id": s_id, "name": s_name, "kind": s_kind}
        nodes[t_id] = {"id": t_id, "name": t_name, "kind": t_kind}
        adj[s_id].add(t_id)
        adj[t_id].add(s_id)
        edges_list.append((s_id, t_id, r_type))

    if not nodes:
        return {
            "algorithm": "CommunityDetection",
            "total_communities": 0,
            "communities": [],
            "inter_community_bridges": [],
            "interpretation": "No entities found for community detection.",
            "limitations": "Graph was empty for the provided criteria.",
        }

    labels: dict[str, str] = {node_id: node_id for node_id in nodes}
    node_order = sorted(list(nodes.keys()))

    for _ in range(max_iterations):
        changed = False
        for node in node_order:
            neighbors = adj[node]
            if not neighbors:
                continue

            label_counts: dict[str, int] = defaultdict(int)
            for nbr in neighbors:
                label_counts[labels[nbr]] += 1

            max_freq = max(label_counts.values())
            best_labels = [lbl for lbl, cnt in label_counts.items() if cnt == max_freq]
            best_label = min(best_labels)

            if labels[node] != best_label:
                labels[node] = best_label
                changed = True
        if not changed:
            break

    community_members: dict[str, list[dict[str, str]]] = defaultdict(list)
    for node_id, comm_label in labels.items():
        community_members[comm_label].append(nodes[node_id])

    bridges = []
    seen_bridge = set()
    for s_id, t_id, r_type in edges_list:
        if labels[s_id] != labels[t_id]:
            edge_key = tuple(sorted([s_id, t_id])) + (r_type,)
            if edge_key not in seen_bridge:
                seen_bridge.add(edge_key)
                bridges.append({
                    "from": {"id": s_id, "name": nodes[s_id]["name"], "kind": nodes[s_id]["kind"], "community": labels[s_id]},
                    "to": {"id": t_id, "name": nodes[t_id]["name"], "kind": nodes[t_id]["kind"], "community": labels[t_id]},
                    "relationship_type": r_type,
                })

    formatted_communities = []
    for comm_id, members in community_members.items():
        if len(members) >= min_community_size:
            kind_counts = defaultdict(int)
            for m in members:
                kind_counts[m["kind"]] += 1
            predominant_kind = max(kind_counts.items(), key=lambda x: x[1])[0] if kind_counts else "Unknown"

            formatted_communities.append({
                "community_id": f"comm-{comm_id[:12]}",
                "size": len(members),
                "predominant_kind": predominant_kind,
                "kind_distribution": dict(kind_counts),
                "members": members[:10],
            })

    formatted_communities.sort(key=lambda c: c["size"], reverse=True)

    return {
        "algorithm": "CommunityDetection (LabelPropagation)",
        "total_communities": len(formatted_communities),
        "communities": formatted_communities,
        "inter_community_bridges_count": len(bridges),
        "inter_community_bridges": bridges[:15],
        "interpretation": (
            "Partitions the network into densely interconnected modules or functional clusters. "
            "Inter-community bridges indicate critical coupling points where cross-boundary coordination or cascading failures occur."
        ),
        "limitations": "Uses deterministic asynchronous label propagation; community labels reflect local density.",
    }


def detect_critical_dependencies(
    scope_kind: str = "",
    relationship_types: Optional[list[str]] = None,
    top_k: int = 10,
    graph_name: Optional[str] = None,
) -> dict[str, Any]:
    """
    Detect articulation points (cut vertices) and single points of failure
    whose failure or removal disconnects parts of the graph or isolates subsystems.
    """
    rel_filter = ""
    params: dict[str, Any] = {}
    if relationship_types:
        rel_filter = "WHERE type(r) IN $rels"
        params["rels"] = relationship_types

    query = f"""
    MATCH (source:Entity)-[r]->(target:Entity)
    {rel_filter}
    RETURN source.id, source.name, source.kind, target.id, target.name, target.kind
    """
    rows = execute_ro_query(query, params=params, graph_name=graph_name)

    nodes: dict[str, dict[str, str]] = {}
    adj: dict[str, set[str]] = defaultdict(set)
    in_degrees: dict[str, int] = defaultdict(int)
    out_degrees: dict[str, int] = defaultdict(int)

    for s_id, s_name, s_kind, t_id, t_name, t_kind in rows:
        nodes[s_id] = {"id": s_id, "name": s_name, "kind": s_kind}
        nodes[t_id] = {"id": t_id, "name": t_name, "kind": t_kind}
        adj[s_id].add(t_id)
        adj[t_id].add(s_id)
        out_degrees[s_id] += 1
        in_degrees[t_id] += 1

    timer = 0
    tin: dict[str, int] = {}
    low: dict[str, int] = {}
    visited: set[str] = set()
    articulation_points: set[str] = set()

    def dfs(u: str, p: Optional[str] = None) -> None:
        nonlocal timer
        visited.add(u)
        tin[u] = low[u] = timer
        timer += 1
        children = 0

        for v in adj[u]:
            if v == p:
                continue
            if v in visited:
                low[u] = min(low[u], tin[v])
            else:
                dfs(v, u)
                low[u] = min(low[u], low[v])
                if low[v] >= tin[u] and p is not None:
                    articulation_points.add(u)
                children += 1

        if p is None and children > 1:
            articulation_points.add(u)

    for node in sorted(list(adj.keys())):
        if node not in visited:
            dfs(node)

    bottleneck_candidates = []
    for node_id, info in nodes.items():
        if scope_kind and info["kind"].lower() != scope_kind.lower():
            continue

        is_cut_vertex = node_id in articulation_points
        in_deg = in_degrees.get(node_id, 0)
        out_deg = out_degrees.get(node_id, 0)
        total_deg = in_deg + out_deg

        risk_score = (3.0 if is_cut_vertex else 0.0) + (in_deg * 0.8) + (out_deg * 0.4)

        bottleneck_candidates.append({
            "id": node_id,
            "name": info["name"],
            "kind": info["kind"],
            "is_articulation_point": is_cut_vertex,
            "in_degree": in_deg,
            "out_degree": out_deg,
            "total_degree": total_deg,
            "criticality_score": round(risk_score, 2),
            "vulnerability_type": (
                "ARTICULATION_POINT (Single Point of Failure): Removal disconnects graph partitions."
                if is_cut_vertex
                else "HIGH_DEPENDENCY_HUB: Many entities depend on this node."
                if in_deg >= 3
                else "MODERATE_DEPENDENCY"
            ),
        })

    bottleneck_candidates.sort(key=lambda x: (x["is_articulation_point"], x["criticality_score"]), reverse=True)
    top_candidates = bottleneck_candidates[:top_k]

    return {
        "algorithm": "CriticalDependencyDetection",
        "scope_kind": scope_kind or "all",
        "articulation_points_count": len([c for c in bottleneck_candidates if c["is_articulation_point"]]),
        "total_analyzed": len(bottleneck_candidates),
        "critical_dependencies": top_candidates,
        "interpretation": (
            "Discovers single points of failure (articulation points) and heavy dependencies. "
            "Entities flagged as articulation points cause network fragmentation if compromised, delayed, or removed."
        ),
        "recommendations": [
            f"Add redundancy or alternative fallback paths around cut vertex '{c['name']}' ({c['id']})."
            for c in top_candidates if c["is_articulation_point"]
        ][:5],
    }
