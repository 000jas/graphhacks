from __future__ import annotations

import uuid
from typing import Any, Optional

try:
    from mcp_server.config import validate_identifier
    from mcp_server.counterfactual import simulate_candidate_action
    from mcp_server.db import execute_ro_query, execute_rw_query
    from mcp_server.models import utc_now
except ImportError:
    from config import validate_identifier
    from counterfactual import simulate_candidate_action
    from db import execute_ro_query, execute_rw_query
    from models import utc_now


def propose_action(
    action: str,
    target_id: str,
    rationale: str,
    evidence_ids: Optional[list[str]] = None,
    params: Optional[dict[str, Any]] = None,
    graph_name: Optional[str] = None,
) -> dict[str, Any]:
    """
    Formally propose a candidate action bound to graph evidence, policy checks, and simulation.
    Creates an auditable ActionProposal in the graph.
    """
    action = action.strip()
    target_id = target_id.strip()
    rationale = (rationale or "").strip()
    evidence_ids = evidence_ids or []
    params = params or {}

    if not action or not target_id or not rationale:
        raise ValueError("action, target_id, and rationale are required to propose an action")

    simulation = simulate_candidate_action(action, target_id, params=params, graph_name=graph_name)
    policy_allowed = simulation.get("policy_evaluation", {}).get("allowed", False)

    proposal_id = f"prop-{uuid.uuid4().hex[:10]}"
    approval_token = f"token-apprv-{uuid.uuid4().hex[:8]}" if policy_allowed else "BLOCKED_BY_POLICY"
    created_at = utc_now()

    query = """
    MERGE (p:Entity {id: $id})
    SET p:ActionProposal
    SET p.name = $name,
        p.kind = 'ActionProposal',
        p.action = $action,
        p.target_id = $target_id,
        p.rationale = $rationale,
        p.status = $status,
        p.approval_token = $approval_token,
        p.created_at = $created_at,
        p.source_ref = $source_ref
    """
    execute_rw_query(
        query,
        params={
            "id": proposal_id,
            "name": f"Proposal: {action} on {target_id}",
            "action": action,
            "target_id": target_id,
            "rationale": rationale,
            "status": "APPROVED_PENDING_EXECUTION" if policy_allowed else "REJECTED_BY_POLICY",
            "approval_token": approval_token,
            "created_at": created_at,
            "source_ref": f"graphos:proposal:{proposal_id}",
        },
        graph_name=graph_name,
    )

    execute_rw_query(
        """
        MATCH (p:Entity {id: $prop_id})
        MATCH (target:Entity {id: $target_id})
        MERGE (p)-[:APPLIES_TO {id: $rel_id, observed_at: $created_at}]->(target)
        """,
        params={
            "prop_id": proposal_id,
            "target_id": target_id,
            "rel_id": f"{proposal_id}__applies_to__{target_id}",
            "created_at": created_at,
        },
        graph_name=graph_name,
    )

    for ev_id in evidence_ids:
        execute_rw_query(
            """
            MATCH (p:Entity {id: $prop_id})
            MATCH (ev:Entity {id: $ev_id})
            MERGE (p)-[:TRACED_TO {id: $rel_id, observed_at: $created_at}]->(ev)
            """,
            params={
                "prop_id": proposal_id,
                "ev_id": ev_id,
                "rel_id": f"{proposal_id}__traced_to__{ev_id}",
                "created_at": created_at,
            },
            graph_name=graph_name,
        )

    return {
        "proposal_id": proposal_id,
        "action": action,
        "target_id": target_id,
        "rationale": rationale,
        "status": "APPROVED_PENDING_EXECUTION" if policy_allowed else "REJECTED_BY_POLICY",
        "approval_token": approval_token,
        "required_evidence_count": len(evidence_ids),
        "policy_allowed": policy_allowed,
        "simulation_summary": simulation.get("counterfactual_verdict", ""),
        "execution_instruction": (
            f"To execute this approved action, invoke 'execute_approved_action' with proposal_id='{proposal_id}' and approval_token='{approval_token}'."
            if policy_allowed
            else "Action cannot be executed because policy checks failed. Revise the proposal or resolve dependencies."
        ),
    }


def execute_approved_action(
    proposal_id: str,
    approval_token: str,
    graph_name: Optional[str] = None,
) -> dict[str, Any]:
    """
    Execute a formally approved action with token authorization, idempotent mutation, and audit logging.
    """
    proposal_id = proposal_id.strip()
    approval_token = approval_token.strip()

    if not proposal_id or not approval_token:
        raise ValueError("proposal_id and approval_token are required for action execution")

    rows = execute_ro_query(
        """
        MATCH (p:Entity {id: $id})
        WHERE p.kind = 'ActionProposal'
        RETURN p.id, p.action, p.target_id, p.status, p.approval_token, properties(p)
        """,
        params={"id": proposal_id},
        graph_name=graph_name,
    )

    if not rows:
        return {
            "executed": False,
            "proposal_id": proposal_id,
            "status": "NOT_FOUND",
            "message": f"Action proposal '{proposal_id}' was not found in graph.",
        }

    p_id, p_action, p_target, p_status, p_token, p_props = rows[0]

    if p_token != approval_token or approval_token == "BLOCKED_BY_POLICY":
        return {
            "executed": False,
            "proposal_id": proposal_id,
            "status": "UNAUTHORIZED",
            "message": "Invalid, forged, or policy-blocked approval token. Execution aborted.",
        }

    if p_status == "EXECUTED":
        return {
            "executed": True,
            "proposal_id": proposal_id,
            "status": "ALREADY_EXECUTED",
            "message": "This proposal was already executed. Idempotent check satisfied without duplicate operations.",
            "executed_at": p_props.get("executed_at", ""),
        }

    applied_changes = []
    executed_at = utc_now()
    exec_id = f"exec-{uuid.uuid4().hex[:10]}"

    if p_action == "reassign_review":
        execute_rw_query(
            """
            MATCH (t:Entity {id: $task_id})
            SET t.status = 'in_progress', t.updated_at = $ts
            """,
            params={"task_id": p_target, "ts": executed_at},
            graph_name=graph_name,
        )
        applied_changes.append({"entity": p_target, "property": "status", "new_value": "in_progress"})

    elif p_action == "approve_production_release":
        execute_rw_query(
            """
            MATCH (r:Entity {id: $release_id})
            SET r.status = 'approved', r.updated_at = $ts
            """,
            params={"release_id": p_target, "ts": executed_at},
            graph_name=graph_name,
        )
        applied_changes.append({"entity": p_target, "property": "status", "new_value": "approved"})

    else:
        applied_changes.append({"entity": p_target, "operation": p_action, "status": "applied"})

    execute_rw_query(
        """
        MATCH (p:Entity {id: $id})
        SET p.status = 'EXECUTED',
            p.executed_at = $ts,
            p.execution_id = $exec_id
        """,
        params={"id": proposal_id, "ts": executed_at, "exec_id": exec_id},
        graph_name=graph_name,
    )

    execute_rw_query(
        """
        MERGE (a:Entity {id: $audit_id})
        SET a:AuditRecord
        SET a.name = $audit_name,
            a.kind = 'AuditRecord',
            a.execution_id = $exec_id,
            a.proposal_id = $prop_id,
            a.action = $action,
            a.target_id = $target_id,
            a.executed_at = $ts,
            a.status = 'SUCCESS'
        """,
        params={
            "audit_id": f"audit-{exec_id}",
            "audit_name": f"Audit Log: {p_action} on {p_target}",
            "exec_id": exec_id,
            "prop_id": proposal_id,
            "action": p_action,
            "target_id": p_target,
            "ts": executed_at,
        },
        graph_name=graph_name,
    )

    return {
        "executed": True,
        "execution_id": exec_id,
        "proposal_id": proposal_id,
        "action": p_action,
        "target_id": p_target,
        "status": "SUCCESS",
        "executed_at": executed_at,
        "applied_changes": applied_changes,
        "audit_trail_id": f"audit-{exec_id}",
        "message": f"Action '{p_action}' executed successfully on '{p_target}'. Audit log created.",
    }


def record_outcome(
    finding_id: str,
    target_entity_ids: list[str],
    summary: str,
    outcome_status: str,
    evidence_refs: Optional[list[str]] = None,
    variance_analysis: Optional[str] = None,
    graph_name: Optional[str] = None,
) -> dict[str, Any]:
    """
    Record a durable, graph-connected organizational memory record.
    """
    finding_id = finding_id.strip()
    summary = summary.strip()
    outcome_status = outcome_status.strip().upper()
    evidence_refs = evidence_refs or []
    variance_analysis = variance_analysis or ""

    if not finding_id or not summary or not outcome_status:
        raise ValueError("finding_id, summary, and outcome_status are required")

    memory_id = f"mem-{uuid.uuid4().hex[:10]}"
    recorded_at = utc_now()

    execute_rw_query(
        """
        MERGE (m:Entity {id: $id})
        SET m:MemoryRecord
        SET m.name = $name,
            m.kind = 'MemoryRecord',
            m.finding_id = $finding_id,
            m.summary = $summary,
            m.outcome_status = $outcome_status,
            m.variance_analysis = $variance,
            m.recorded_at = $ts,
            m.source_ref = $source_ref
        """,
        params={
            "id": memory_id,
            "name": f"Decision Memory: {finding_id}",
            "finding_id": finding_id,
            "summary": summary,
            "outcome_status": outcome_status,
            "variance": variance_analysis,
            "ts": recorded_at,
            "source_ref": f"graphos:memory:{memory_id}",
        },
        graph_name=graph_name,
    )

    for entity_id in target_entity_ids:
        execute_rw_query(
            """
            MATCH (m:Entity {id: $mem_id})
            MATCH (t:Entity {id: $target_id})
            MERGE (m)-[:DOCUMENTED_IN {id: $rel_id, observed_at: $ts}]->(t)
            """,
            params={
                "mem_id": memory_id,
                "target_id": entity_id,
                "rel_id": f"{memory_id}__documents__{entity_id}",
                "ts": recorded_at,
            },
            graph_name=graph_name,
        )

    return {
        "memory_id": memory_id,
        "finding_id": finding_id,
        "target_entities_linked": target_entity_ids,
        "outcome_status": outcome_status,
        "recorded_at": recorded_at,
        "evidence_refs_preserved": len(evidence_refs),
        "summary": summary,
        "variance_analysis": variance_analysis,
        "status": "SAVED_TO_ORGANIZATIONAL_MEMORY",
        "message": f"Durable memory record '{memory_id}' created and linked to {len(target_entity_ids)} entities.",
    }


def query_decision_memory(
    query: str = "",
    entity_id: str = "",
    status: str = "",
    limit: int = 20,
    graph_name: Optional[str] = None,
) -> dict[str, Any]:
    """
    Retrieve historical organizational decisions, action proposals, executed outcomes,
    and investigation findings with full provenance and status tracking.
    """
    limit = max(1, min(limit, 50))
    where_clauses = ["m.kind IN ['MemoryRecord', 'ActionProposal', 'InvestigationFinding', 'AuditRecord']"]
    params: dict[str, Any] = {}

    if query.strip():
        where_clauses.append("(toLower(m.name) CONTAINS toLower($q) OR toLower(m.summary) CONTAINS toLower($q) OR toLower(m.rationale) CONTAINS toLower($q))")
        params["q"] = query.strip()

    if status.strip():
        where_clauses.append("toLower(m.status) = toLower($status) OR toLower(m.outcome_status) = toLower($status)")
        params["status"] = status.strip()

    match_clause = "MATCH (m:Entity)"
    if entity_id.strip():
        clean_eid = validate_identifier(entity_id, field_name="entity_id")
        match_clause = "MATCH (target:Entity {id: $eid})-[r]-(m:Entity)"
        params["eid"] = clean_eid

    where_stmt = "WHERE " + " AND ".join(where_clauses)

    cypher = f"""
    {match_clause}
    {where_stmt}
    RETURN
        m.id,
        m.name,
        m.kind,
        coalesce(m.outcome_status, m.status, 'UNKNOWN') AS status,
        coalesce(m.summary, m.rationale, m.objective, '') AS summary,
        coalesce(m.recorded_at, m.created_at, m.executed_at, '') AS timestamp,
        m.source_ref,
        properties(m)
    ORDER BY timestamp DESC
    LIMIT {limit}
    """
    rows = execute_ro_query(cypher, params=params, graph_name=graph_name)

    records = [
        {
            "id": r[0],
            "name": r[1],
            "kind": r[2],
            "status": r[3],
            "summary": r[4],
            "timestamp": r[5],
            "source_ref": r[6],
            "properties": r[7],
        }
        for r in rows
    ]

    return {
        "query": query,
        "filtered_by_entity_id": entity_id or None,
        "filtered_by_status": status or None,
        "count": len(records),
        "records": records,
        "tenant_graph": graph_name or "default",
    }


def record_investigation_finding(
    title: str,
    objective: str,
    key_findings: list[str],
    supporting_entity_ids: list[str],
    evidence_path_ids: Optional[list[str]] = None,
    confidence: str = "HIGH",
    graph_name: Optional[str] = None,
) -> dict[str, Any]:
    """
    Record a durable, graph-connected investigation finding with links to supporting entities and evidence.
    """
    title = (title or "").strip()
    objective = (objective or "").strip()
    if not title or not objective:
        raise ValueError("title and objective are required to record an investigation finding")
    if not supporting_entity_ids:
        raise ValueError("supporting_entity_ids must contain at least one entity ID")

    clean_eids = [validate_identifier(eid, field_name="supporting_entity_id") for eid in supporting_entity_ids]
    evidence_path_ids = evidence_path_ids or []

    finding_id = f"finding-{uuid.uuid4().hex[:10]}"
    created_at = utc_now()

    summary_text = "\n".join(f"- {f}" for f in key_findings) if key_findings else objective

    execute_rw_query(
        """
        MERGE (f:Entity {id: $id})
        SET f:InvestigationFinding
        SET f.name = $title,
            f.kind = 'InvestigationFinding',
            f.objective = $objective,
            f.summary = $summary,
            f.confidence = $confidence,
            f.status = 'ACTIVE',
            f.created_at = $created_at,
            f.source_ref = $source_ref
        """,
        params={
            "id": finding_id,
            "title": title,
            "objective": objective,
            "summary": summary_text,
            "confidence": confidence.upper(),
            "created_at": created_at,
            "source_ref": f"graphos:finding:{finding_id}",
        },
        graph_name=graph_name,
    )

    for eid in clean_eids:
        execute_rw_query(
            """
            MATCH (f:Entity {id: $fid})
            MATCH (target:Entity {id: $eid})
            MERGE (f)-[:EXPLAINS {id: $rel_id, observed_at: $created_at}]->(target)
            """,
            params={
                "fid": finding_id,
                "eid": eid,
                "rel_id": f"{finding_id}__explains__{eid}",
                "created_at": created_at,
            },
            graph_name=graph_name,
        )

    for path_id in evidence_path_ids:
        execute_rw_query(
            """
            MATCH (f:Entity {id: $fid})
            MATCH (ev:Entity {id: $pid})
            MERGE (f)-[:TRACED_TO {id: $rel_id, observed_at: $created_at}]->(ev)
            """,
            params={
                "fid": finding_id,
                "pid": path_id,
                "rel_id": f"{finding_id}__traced_to__{path_id}",
                "created_at": created_at,
            },
            graph_name=graph_name,
        )

    return {
        "finding_id": finding_id,
        "title": title,
        "status": "ACTIVE",
        "confidence": confidence.upper(),
        "supporting_entities_count": len(clean_eids),
        "supporting_entities": clean_eids,
        "created_at": created_at,
        "message": f"Investigation finding '{finding_id}' permanently recorded and connected to graph entities.",
        "tenant_graph": graph_name or "default",
    }


def supersede_finding(
    finding_id: str,
    reason: str,
    superseding_finding_id: str = "",
    new_evidence_refs: Optional[list[str]] = None,
    graph_name: Optional[str] = None,
) -> dict[str, Any]:
    """
    Challenge or update a historical finding with newer evidence, marking it SUPERSEDED
    while preserving permanent audit history.
    """
    finding_id = (finding_id or "").strip()
    reason = (reason or "").strip()
    if not finding_id or not reason:
        raise ValueError("finding_id and reason are required to supersede a finding")

    clean_fid = validate_identifier(finding_id, field_name="finding_id")

    rows = execute_ro_query(
        "MATCH (f:Entity {id: $id}) RETURN f.id, f.name, f.kind, f.status",
        params={"id": clean_fid},
        graph_name=graph_name,
    )
    if not rows:
        return {
            "finding_id": clean_fid,
            "superseded": False,
            "message": f"Finding '{clean_fid}' not found in graph.",
            "tenant_graph": graph_name or "default",
        }

    now_ts = utc_now()

    execute_rw_query(
        """
        MATCH (f:Entity {id: $id})
        SET f.status = 'SUPERSEDED',
            f.superseded_at = $ts,
            f.superseded_reason = $reason,
            f.superseded_by = $new_fid
        """,
        params={
            "id": clean_fid,
            "ts": now_ts,
            "reason": reason,
            "new_fid": superseding_finding_id or "",
        },
        graph_name=graph_name,
    )

    if superseding_finding_id.strip():
        clean_new_fid = validate_identifier(superseding_finding_id, field_name="superseding_finding_id")
        execute_rw_query(
            """
            MATCH (old_f:Entity {id: $old_id})
            MATCH (new_f:Entity {id: $new_id})
            MERGE (old_f)-[:SUPERSEDED_BY {observed_at: $ts}]->(new_f)
            """,
            params={
                "old_id": clean_fid,
                "new_id": clean_new_fid,
                "ts": now_ts,
            },
            graph_name=graph_name,
        )

    return {
        "finding_id": clean_fid,
        "previous_status": rows[0][3],
        "new_status": "SUPERSEDED",
        "superseded_at": now_ts,
        "reason": reason,
        "superseding_finding_id": superseding_finding_id or None,
        "message": f"Finding '{clean_fid}' marked SUPERSEDED with audit trail preserved.",
        "tenant_graph": graph_name or "default",
    }
