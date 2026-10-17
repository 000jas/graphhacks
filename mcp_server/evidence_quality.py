from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from mcp_server.config import settings, validate_identifier
    from mcp_server.db import execute_ro_query
except ImportError:
    from config import settings, validate_identifier
    from db import execute_ro_query

logger = logging.getLogger("graphos.mcp.evidence")

CURRENT_EVALUATION_TIME = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)


def parse_iso_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO timestamp strings with timezone handling."""
    if not dt_str:
        return None
    try:
        clean_str = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def evaluate_evidence_quality(
    entity_id: str = "",
    max_depth: int = 2,
    stale_days_threshold: int = 30,
    tenant_graph: str = "",
) -> dict[str, Any]:
    """
    Evaluate evidence freshness, provenance verification rates, confidence distribution,
    and missing evidence records across the graph or an entity neighborhood.
    """
    target_graph = settings.validate_graph_name(tenant_graph)
    depth = max(1, min(max_depth, 3))

    if entity_id:
        clean_id = validate_identifier(entity_id, field_name="entity_id")
        query = f"""
        MATCH (start)-[*1..{depth}]-(n)
        WHERE (toString(id(start)) = $eid OR start.id = $eid OR start.name = $eid)
        MATCH (n)-[r]->(m)
        RETURN
            coalesce(startNode(r).id, toString(id(startNode(r)))) AS src_id,
            coalesce(startNode(r).name, startNode(r).id, toString(id(startNode(r)))) AS src_name,
            type(r) AS rel_type,
            coalesce(endNode(r).id, toString(id(endNode(r)))) AS tgt_id,
            coalesce(endNode(r).name, endNode(r).id, toString(id(endNode(r)))) AS tgt_name,
            r.source_record_id AS source_record_id,
            r.observed_at AS observed_at,
            r.confidence AS confidence,
            properties(r) AS props
        LIMIT 200
        """
        params: dict[str, Any] = {"eid": clean_id}
        scope_desc = f"Neighborhood of '{clean_id}' (depth {depth})"
    else:
        query = """
        MATCH (a)-[r]->(b)
        RETURN
            coalesce(a.id, toString(id(a))) AS src_id,
            coalesce(a.name, a.id, toString(id(a))) AS src_name,
            type(r) AS rel_type,
            coalesce(b.id, toString(id(b))) AS tgt_id,
            coalesce(b.name, b.id, toString(id(b))) AS tgt_name,
            r.source_record_id AS source_record_id,
            r.observed_at AS observed_at,
            r.confidence AS confidence,
            properties(r) AS props
        LIMIT 300
        """
        params = {}
        scope_desc = "Whole graph sample"

    rows = execute_ro_query(query, params=params, graph_name=target_graph)

    if not rows:
        return {
            "scope": scope_desc,
            "total_relationships_inspected": 0,
            "verification_rate": 0.0,
            "evidence_quality_score": 0.0,
            "quality_rating": "INSUFFICIENT_DATA",
            "message": "No relationships found within the specified scope.",
            "tenant_graph": target_graph,
        }

    total_edges = len(rows)
    verified_count = 0
    confidence_values: list[float] = []
    stale_count = 0
    missing_source_edges: list[dict[str, Any]] = []
    stale_edges: list[dict[str, Any]] = []

    for src_id, src_name, r_type, tgt_id, tgt_name, s_rec, obs_at, conf, props in rows:
        if s_rec:
            verified_count += 1
        else:
            if len(missing_source_edges) < 10:
                missing_source_edges.append({
                    "from": {"id": src_id, "name": src_name},
                    "relationship": r_type,
                    "to": {"id": tgt_id, "name": tgt_name},
                    "issue": "Missing source_record_id provenance reference",
                })

        c_val = float(conf) if isinstance(conf, (int, float)) else 0.8
        confidence_values.append(c_val)

        dt = parse_iso_datetime(obs_at)
        if dt:
            age_days = (CURRENT_EVALUATION_TIME - dt).days
            if age_days > stale_days_threshold:
                stale_count += 1
                if len(stale_edges) < 10:
                    stale_edges.append({
                        "from": {"id": src_id, "name": src_name},
                        "relationship": r_type,
                        "to": {"id": tgt_id, "name": tgt_name},
                        "observed_at": obs_at,
                        "age_days": age_days,
                    })

    verif_rate = round(verified_count / max(1, total_edges), 2)
    avg_conf = round(sum(confidence_values) / max(1, len(confidence_values)), 2)
    min_conf = round(min(confidence_values), 2) if confidence_values else 0.0
    freshness_rate = round((total_edges - stale_count) / max(1, total_edges), 2)

    score = round((verif_rate * 0.45) + (avg_conf * 0.35) + (freshness_rate * 0.20), 2)

    if score >= 0.80:
        rating = "HIGH"
    elif score >= 0.50:
        rating = "MEDIUM"
    else:
        rating = "LOW"

    return {
        "scope": scope_desc,
        "evaluated_at": CURRENT_EVALUATION_TIME.isoformat(),
        "total_relationships_inspected": total_edges,
        "evidence_quality_score": score,
        "quality_rating": rating,
        "verification_metrics": {
            "verified_relationships_count": verified_count,
            "verification_rate": verif_rate,
            "unverified_relationships_count": total_edges - verified_count,
        },
        "confidence_metrics": {
            "average_confidence": avg_conf,
            "minimum_confidence": min_conf,
            "maximum_confidence": round(max(confidence_values), 2) if confidence_values else 0.0,
        },
        "freshness_metrics": {
            "stale_days_threshold": stale_days_threshold,
            "stale_relationships_count": stale_count,
            "freshness_rate": freshness_rate,
        },
        "unverified_evidence_samples": missing_source_edges,
        "stale_evidence_samples": stale_edges,
        "limitations": [
            "Graph paths represent correlation and registered dependency, not autonomous causation.",
            "Unverified edges lack cryptographically signed source document references.",
            "Relationships without observed_at timestamps cannot be certified for temporal freshness.",
        ],
        "tenant_graph": target_graph,
    }


def detect_conflicting_evidence(
    scope_entity_ids: Optional[list[str]] = None,
    tenant_graph: str = "",
) -> dict[str, Any]:
    """
    Detect conflicting evidence, contradictory relationship states,
    and mutually exclusive claims across entities.
    """
    target_graph = settings.validate_graph_name(tenant_graph)
    clean_ids = [validate_identifier(eid, field_name="entity_id") for eid in (scope_entity_ids or [])]

    scope_filter = ""
    params: dict[str, Any] = {}
    if clean_ids:
        scope_filter = "WHERE a.id IN $eids OR b.id IN $eids"
        params["eids"] = clean_ids

    conflicts: list[dict[str, Any]] = []

    blocked_conflict_query = f"""
    MATCH (task:Entity)-[:BLOCKED_BY]->(blocker:Entity)
    {scope_filter}
    WHERE toLower(task.status) IN ['complete', 'completed', 'approved', 'passed']
      AND toLower(blocker.status) IN ['in_progress', 'delayed', 'blocked', 'failed', 'awaiting_review']
    RETURN task.id, task.name, task.status, blocker.id, blocker.name, blocker.status
    LIMIT 20
    """
    rows1 = execute_ro_query(blocked_conflict_query, params=params, graph_name=target_graph)
    for t_id, t_name, t_stat, b_id, b_name, b_stat in rows1:
        conflicts.append({
            "conflict_type": "RESOLVED_TASK_BLOCKED_BY_INCOMPLETE_DEPENDENCY",
            "severity": "HIGH",
            "entity_id": t_id,
            "description": f"Task '{t_name}' is marked '{t_stat}', but its prerequisite '{b_name}' is currently '{b_stat}'.",
            "evidence": {"task": {"id": t_id, "status": t_stat}, "prerequisite": {"id": b_id, "status": b_stat}},
            "remediation": "Audit whether the prerequisite was bypassed or if the task status was prematurely updated.",
        })

    assignee_conflict_query = """
    MATCH (task:Entity)-[:ASSIGNED_TO]->(person:Entity)-[:HAS_EVENT]->(event:Entity)
    WHERE toLower(task.status) IN ['in_progress', 'pending', 'awaiting_review']
      AND (toLower(person.availability) IN ['on_leave', 'unavailable', 'pto']
           OR toLower(event.name) CONTAINS 'leave' OR toLower(event.name) CONTAINS 'pto')
    RETURN task.id, task.name, task.status, person.id, person.name, person.availability, event.name
    LIMIT 20
    """
    rows2 = execute_ro_query(assignee_conflict_query, params=params, graph_name=target_graph)
    for t_id, t_name, t_stat, p_id, p_name, p_avail, e_name in rows2:
        conflicts.append({
            "conflict_type": "UNAVAILABLE_ASSIGNEE_ON_ACTIVE_TASK",
            "severity": "HIGH",
            "entity_id": t_id,
            "description": f"Task '{t_name}' ({t_stat}) is assigned to '{p_name}', who is unavailable (availability: '{p_avail}', event: '{e_name}').",
            "evidence": {"task_id": t_id, "assignee_id": p_id, "availability": p_avail, "event": e_name},
            "remediation": "Reassign task to an available reviewer using 'reassign_review' action.",
        })

    dep_conflict_query = """
    MATCH (pr:Entity)-[:INTRODUCES_DEPENDENCY]->(dep:Entity)-[:GOVERNED_BY]->(policy:Entity)
    WHERE dep.proposed_version IS NOT NULL
      AND (toLower(policy.requirement) CONTAINS 'prohibit'
           OR toLower(policy.requirement) CONTAINS 'disallow'
           OR toLower(dep.status) = 'flagged')
    RETURN pr.id, pr.name, dep.id, dep.name, dep.proposed_version, policy.name, policy.requirement
    LIMIT 20
    """
    rows3 = execute_ro_query(dep_conflict_query, params=params, graph_name=target_graph)
    for pr_id, pr_name, dep_id, dep_name, ver, pol_name, req in rows3:
        conflicts.append({
            "conflict_type": "POLICY_DISALLOWED_DEPENDENCY",
            "severity": "CRITICAL",
            "entity_id": pr_id,
            "description": f"PR '{pr_name}' introduces '{dep_name}' v{ver}, which conflicts with policy '{pol_name}'.",
            "evidence": {"pr_id": pr_id, "dependency": dep_name, "version": ver, "policy_requirement": req},
            "remediation": "Update or reject pull request to comply with security dependency policies.",
        })

    return {
        "total_conflicts_detected": len(conflicts),
        "conflicts": conflicts,
        "has_conflicting_evidence": len(conflicts) > 0,
        "interpretation": (
            f"Detected {len(conflicts)} evidence conflict(s) across investigated entities."
            if conflicts
            else "No direct contradictory claims or status conflicts found in graph evidence."
        ),
        "tenant_graph": target_graph,
    }


def inspect_temporal_graph(
    entity_id: str,
    as_of_timestamp: Optional[str] = None,
    time_window_days: Optional[int] = None,
    tenant_graph: str = "",
) -> dict[str, Any]:
    """
    Inspect the temporal evolution of relationships and events connected to an entity,
    identifying historical milestones, recent changes, and observation timelines.
    """
    entity_id = validate_identifier(entity_id, field_name="entity_id")
    target_graph = settings.validate_graph_name(tenant_graph)

    query = """
    MATCH (n)-[r]-(other)
    WHERE (toString(id(n)) = $eid OR n.id = $eid OR n.name = $eid)
    RETURN
        type(r) AS rel_type,
        coalesce(other.id, toString(id(other))) AS other_id,
        coalesce(other.name, other.id, toString(id(other))) AS other_name,
        coalesce(other.kind, labels(other)[0], 'Entity') AS other_kind,
        r.observed_at AS observed_at,
        r.created_at AS created_at,
        r.status AS rel_status,
        properties(r) AS props
    """
    rows = execute_ro_query(query, params={"eid": entity_id}, graph_name=target_graph)

    timeline_events: list[dict[str, Any]] = []
    undated_connections: list[dict[str, Any]] = []

    as_of_dt = parse_iso_datetime(as_of_timestamp)

    for r_type, o_id, o_name, o_kind, obs_at, cre_at, r_status, props in rows:
        ts_str = obs_at or cre_at or props.get("date") or props.get("timestamp")
        dt = parse_iso_datetime(ts_str)

        entry = {
            "relationship_type": r_type,
            "connected_entity": {"id": o_id, "name": o_name, "kind": o_kind},
            "status": r_status or "active",
            "timestamp": ts_str,
        }

        if dt:
            if as_of_dt and dt > as_of_dt:
                continue

            entry["parsed_dt"] = dt
            timeline_events.append(entry)
        else:
            undated_connections.append(entry)

    timeline_events.sort(key=lambda x: x["parsed_dt"])
    for e in timeline_events:
        e.pop("parsed_dt", None)

    return {
        "entity_id": entity_id,
        "as_of_evaluation": as_of_timestamp or "LATEST",
        "total_connected_relationships": len(rows),
        "timestamped_timeline_events_count": len(timeline_events),
        "chronological_timeline": timeline_events,
        "undated_relationships_count": len(undated_connections),
        "undated_relationships_sample": undated_connections[:10],
        "tenant_graph": target_graph,
    }
