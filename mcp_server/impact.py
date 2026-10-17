from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

try:
    from mcp_server.config import settings, validate_identifier
    from mcp_server.db import execute_ro_query
except ImportError:
    from config import settings, validate_identifier
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


def assess_change_risk_and_impact(
    proposed_change_type: str,
    target_entity_id: str,
    parameters: Optional[dict[str, Any]] = None,
    max_depth: int = 4,
    tenant_graph: str = "",
) -> dict[str, Any]:
    """
    Perform deep graph-guided impact and risk analysis for proposed operational or architectural changes,
    identifying critical cascades, alternative fallback paths, isolated components, and unresolved prerequisites.
    """
    target_entity_id = target_entity_id.strip()
    if not target_entity_id:
        raise ValueError("target_entity_id must not be empty")

    clean_target_id = validate_identifier(target_entity_id, field_name="target_entity_id")
    target_graph = settings.validate_graph_name(tenant_graph)

    base_impact = analyze_graph_impact(
        root_entity_id=clean_target_id,
        direction="both",
        max_depth=max_depth,
        graph_name=target_graph,
    )

    if not base_impact.get("found"):
        return {
            "target_entity_id": clean_target_id,
            "analyzed": False,
            "message": f"Target entity '{clean_target_id}' not found in graph.",
            "tenant_graph": target_graph,
        }

    target_info = base_impact["root_entity"]

    isolated_query = """
    MATCH (target:Entity {id: $tid})-[r]-(neighbor:Entity)
    WITH neighbor, count(r) AS rels_to_target
    MATCH (neighbor)-[all_r]-()
    WITH neighbor, rels_to_target, count(all_r) AS total_rels
    WHERE total_rels = rels_to_target
    RETURN neighbor.id, neighbor.name, neighbor.kind
    LIMIT 20
    """
    isolated_rows = execute_ro_query(isolated_query, params={"tid": clean_target_id}, graph_name=target_graph)
    potentially_isolated = [
        {
            "id": r[0],
            "name": r[1],
            "kind": r[2],
            "risk": f"Entity '{r[1]}' will become completely disconnected/orphaned if '{target_info['name']}' is removed.",
        }
        for r in isolated_rows
    ]

    fallback_analysis = []
    direct_query = """
    MATCH (target:Entity {id: $tid})<-[r]-(dependent:Entity)
    WHERE dependent.kind IN ['Service', 'Release', 'Task', 'Repository']
    RETURN dependent.id, dependent.name, dependent.kind, type(r)
    LIMIT 10
    """
    dependent_rows = execute_ro_query(direct_query, params={"tid": clean_target_id}, graph_name=target_graph)

    for dep_id, dep_name, dep_kind, r_type in dependent_rows:
        alt_query = """
        MATCH (dep:Entity {id: $dep_id})-[r2]->(alt:Entity)
        WHERE alt.id <> $tid AND type(r2) = $rtype
        RETURN alt.id, alt.name, alt.kind
        LIMIT 5
        """
        alt_rows = execute_ro_query(alt_query, params={"dep_id": dep_id, "tid": clean_target_id, "rtype": r_type}, graph_name=target_graph)
        has_fallback = len(alt_rows) > 0
        fallback_analysis.append({
            "dependent_entity": {"id": dep_id, "name": dep_name, "kind": dep_kind},
            "relationship": r_type,
            "has_redundant_connection": has_fallback,
            "fallback_alternatives": [{"id": a[0], "name": a[1], "kind": a[2]} for a in alt_rows],
            "vulnerability": (
                "NO_FALLBACK: Removal causes complete dependency disruption."
                if not has_fallback
                else "REDUNDANT: Alternative connections available."
            ),
        })

    prereq_query = """
    MATCH (target:Entity {id: $tid})-[:BLOCKED_BY|REQUIRES|GOVERNED_BY*1..2]->(req:Entity)
    RETURN DISTINCT req.id, req.name, req.kind, req.status, properties(req)
    LIMIT 15
    """
    prereq_rows = execute_ro_query(prereq_query, params={"tid": clean_target_id}, graph_name=target_graph)
    unresolved_prereqs = []
    for req_id, req_name, req_kind, req_status, req_props in prereq_rows:
        is_unresolved = str(req_status).lower() in ("in_progress", "pending", "awaiting_review", "delayed", "flagged")
        unresolved_prereqs.append({
            "prerequisite_id": req_id,
            "name": req_name,
            "kind": req_kind,
            "status": req_status or "active",
            "is_blocking": is_unresolved,
        })

    blocking_count = len([p for p in unresolved_prereqs if p["is_blocking"]])

    base_score = base_impact["blast_radius"]["score"]
    no_fallback_count = len([f for f in fallback_analysis if not f["has_redundant_connection"]])
    isolated_count = len(potentially_isolated)

    risk_multiplier = 1.0 + (0.2 * no_fallback_count) + (0.25 * isolated_count) + (0.15 * blocking_count)
    composite_risk_score = min(1.0, round(base_score * risk_multiplier, 2))

    if composite_risk_score >= 0.70:
        change_risk_verdict = "HIGH_RISK"
    elif composite_risk_score >= 0.40:
        change_risk_verdict = "MODERATE_RISK"
    else:
        change_risk_verdict = "LOW_RISK"

    interventions = []
    if no_fallback_count > 0:
        interventions.append(f"Establish redundant connections for {no_fallback_count} single-point-of-failure dependent(s).")
    if isolated_count > 0:
        interventions.append(f"Re-home {isolated_count} component(s) that would otherwise be orphaned.")
    if blocking_count > 0:
        interventions.append(f"Resolve {blocking_count} pending prerequisites/reviews prior to executing this change.")

    return {
        "proposed_change_type": proposed_change_type,
        "target_entity": target_info,
        "overall_change_risk_verdict": change_risk_verdict,
        "composite_risk_score": composite_risk_score,
        "deterministic_graph_findings": {
            "direct_dependencies_count": base_impact["blast_radius"]["direct_dependencies_count"],
            "total_transitive_impacted_count": base_impact["blast_radius"]["total_transitive_impacted_count"],
            "critical_assets_impacted": base_impact["blast_radius"]["critical_assets_impacted"],
            "potentially_isolated_components_count": isolated_count,
            "single_points_of_failure_count": no_fallback_count,
            "unresolved_prerequisites_count": blocking_count,
        },
        "potentially_isolated_components": potentially_isolated,
        "fallback_connection_analysis": fallback_analysis,
        "unresolved_prerequisites": unresolved_prereqs,
        "candidate_risk_mitigations": interventions,
        "summary": (
            f"Proposed '{proposed_change_type}' on '{target_info['name']}' ({target_info['kind']}) yields {change_risk_verdict} "
            f"(composite risk: {composite_risk_score}). Discovered {no_fallback_count} dependent(s) with no alternative fallback paths "
            f"and {isolated_count} component(s) facing complete isolation."
        ),
        "tenant_graph": target_graph,
    }
