from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

from db import execute_ro_query

CRITICAL_KINDS = {"Service", "Release", "Environment", "Policy", "Incident"}


def analyze_graph_impact(
    root_entity_id: str,
    direction: str = "downstream",
    max_depth: int = 4,
    graph_name: Optional[str] = None,
) -> dict[str, Any]:
    """
    Compute the blast radius and multi-hop consequence tree of a change, outage, or bottleneck.
    """
    root_entity_id = root_entity_id.strip()
    if not root_entity_id:
        raise ValueError("root_entity_id must not be empty")

    depth = max(1, min(max_depth, 6))

    root_rows = execute_ro_query(
        "MATCH (n:Entity {id: $id}) RETURN n.id, n.name, n.kind, n.status, properties(n)",
        params={"id": root_entity_id},
        graph_name=graph_name,
    )
    if not root_rows:
        return {
            "found": False,
            "root_entity_id": root_entity_id,
            "message": f"Entity '{root_entity_id}' not found in graph.",
        }

    root_info = {
        "id": root_rows[0][0],
        "name": root_rows[0][1],
        "kind": root_rows[0][2],
        "status": root_rows[0][3],
        "properties": root_rows[0][4],
    }

    dir_pattern = "-[r]->" if direction == "downstream" else "<-[r]-" if direction == "upstream" else "-[r]-"

    query = f"""
    MATCH p = (root:Entity {{id: $root_id}}){dir_pattern}(impacted:Entity)
    WHERE impacted.id <> root.id
    RETURN
        impacted.id,
        impacted.name,
        impacted.kind,
        impacted.status,
        type(r),
        properties(r)
    LIMIT 100
    """
    direct_rows = execute_ro_query(query, params={"root_id": root_entity_id}, graph_name=graph_name)

    path_pattern = f"-[*1..{depth}]->" if direction == "downstream" else f"<-[*1..{depth}]-" if direction == "upstream" else f"-[*1..{depth}]-"
    path_query = f"""
    MATCH p = (root:Entity {{id: $root_id}}){path_pattern}(impacted:Entity)
    WHERE impacted.id <> root.id
    RETURN
        impacted.id,
        impacted.name,
        impacted.kind,
        impacted.status,
        length(p) AS hop_distance,
        [node IN nodes(p) | {{id: node.id, name: node.name, kind: node.kind}}] AS path_nodes,
        [rel IN relationships(p) | type(rel)] AS path_relationships
    ORDER BY hop_distance, impacted.name
    LIMIT 100
    """
    path_rows = execute_ro_query(path_query, params={"root_id": root_entity_id}, graph_name=graph_name)

    affected_by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_ids: set[str] = set()
    critical_count = 0
    direct_count = len(direct_rows)

    critical_paths = []

    for row in path_rows:
        e_id, e_name, e_kind, e_status, hops, p_nodes, p_rels = row
        if e_id not in seen_ids:
            seen_ids.add(e_id)
            if e_kind in CRITICAL_KINDS:
                critical_count += 1
            affected_by_kind[e_kind].append({
                "id": e_id,
                "name": e_name,
                "status": e_status,
                "shortest_hops": hops,
            })
        if hops <= 3 and e_kind in CRITICAL_KINDS:
            critical_paths.append({
                "target_entity": {"id": e_id, "name": e_name, "kind": e_kind},
                "hops": hops,
                "chain": [n["name"] for n in p_nodes],
                "relationships": p_rels,
            })

    total_affected = len(seen_ids)

    raw_score = (critical_count * 2.5 + direct_count * 1.5 + (total_affected - direct_count) * 0.8)
    normalized_score = min(1.0, round(raw_score / 25.0, 2))

    if normalized_score >= 0.75:
        severity = "CRITICAL"
    elif normalized_score >= 0.45:
        severity = "HIGH"
    elif normalized_score >= 0.20:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    return {
        "found": True,
        "root_entity": root_info,
        "direction": direction,
        "max_depth_explored": depth,
        "blast_radius": {
            "severity": severity,
            "score": normalized_score,
            "direct_dependencies_count": direct_count,
            "total_transitive_impacted_count": total_affected,
            "critical_assets_impacted": critical_count,
        },
        "impact_by_category": dict(affected_by_kind),
        "critical_impact_chains": critical_paths[:6],
        "summary": (
            f"An event or bottleneck at '{root_info['name']}' ({root_info['kind']}) directly influences {direct_count} entities "
            f"and transitively impacts {total_affected} entities across {len(affected_by_kind)} categories, "
            f"with a {severity} risk level (score: {normalized_score})."
        ),
    }
