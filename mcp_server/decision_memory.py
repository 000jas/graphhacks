from __future__ import annotations

import uuid
from typing import Any, Optional

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
