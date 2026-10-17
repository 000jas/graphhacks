from __future__ import annotations

from typing import Any, Optional

try:
    from mcp_server.db import execute_ro_query
    from mcp_server.impact import analyze_graph_impact
    from mcp_server.policy import check_action_policy
except ImportError:
    from db import execute_ro_query
    from impact import analyze_graph_impact
    from policy import check_action_policy


def simulate_candidate_action(
    action: str,
    target_id: str,
    params: Optional[dict[str, Any]] = None,
    graph_name: Optional[str] = None,
) -> dict[str, Any]:
    """
    Perform Counterfactual Graph Planning:
    Evaluate a candidate intervention against graph topology and policies without mutating state.
    """
    action = action.strip()
    target_id = target_id.strip()
    params = params or {}

    if not action or not target_id:
        raise ValueError("action and target_id are required")

    policy_result = check_action_policy(action, target_id, params, graph_name=graph_name)
    impact_result = analyze_graph_impact(target_id, direction="both", max_depth=3, graph_name=graph_name)

    target_rows = execute_ro_query(
        "MATCH (n:Entity {id: $id}) RETURN n.id, n.name, n.kind, n.status, properties(n)",
        params={"id": target_id},
        graph_name=graph_name,
    )

    if not target_rows:
        return {
            "action": action,
            "target_id": target_id,
            "simulated": False,
            "error": f"Target entity '{target_id}' not found.",
        }

    t_id, t_name, t_kind, t_status, t_props = target_rows[0]

    projected_changes = []
    unblocked_entities = []
    mitigation_steps = []
    reversible = True
    risk_level = "LOW"

    if action == "reassign_review":
        assignee_id = str(params.get("assignee_id", "")).strip()
        assignee_rows = execute_ro_query(
            "MATCH (p:Entity {id: $id}) RETURN p.id, p.name, p.kind, p.availability",
            params={"id": assignee_id},
            graph_name=graph_name,
        )
        assignee_name = assignee_rows[0][1] if assignee_rows else assignee_id

        projected_changes.append({
            "operation": "REMOVE_EDGE",
            "relationship": "ASSIGNED_TO",
            "source_id": target_id,
            "target_id": "current_assignee",
            "reason": "Remove previous assignee who is unavailable / on leave",
        })
        projected_changes.append({
            "operation": "CREATE_EDGE",
            "relationship": "ASSIGNED_TO",
            "source_id": target_id,
            "target_id": assignee_id,
            "reason": f"Assign to qualified and available reviewer ({assignee_name})",
        })
        projected_changes.append({
            "operation": "UPDATE_PROPERTY",
            "entity_id": target_id,
            "property": "status",
            "from_value": t_status,
            "to_value": "in_progress",
        })

        blocked_rows = execute_ro_query(
            """
            MATCH (release:Entity)-[:BLOCKED_BY*1..3]->(task:Entity {id: $task_id})
            RETURN DISTINCT release.id, release.name, release.kind
            """,
            params={"task_id": target_id},
            graph_name=graph_name,
        )
        unblocked_entities = [
            {"id": r[0], "name": r[1], "kind": r[2], "projected_effect": "Unblocks review bottleneck toward release"}
            for r in blocked_rows
        ]

        reversible = True
        risk_level = "LOW" if policy_result.get("allowed") else "HIGH"
        mitigation_steps = [
            f"Send automated onboarding notification to {assignee_name} with PR context.",
            "Set a 24-hour review SLA alert to prevent second-tier bottleneck.",
            "Record reassignment in the release compliance audit trail.",
        ]

    elif action == "bypass_review":
        projected_changes.append({
            "operation": "UPDATE_PROPERTY",
            "entity_id": target_id,
            "property": "status",
            "from_value": t_status,
            "to_value": "bypassed_without_review",
        })
        reversible = False
        risk_level = "CRITICAL"
        mitigation_steps = [
            "DO NOT EXECUTE: Emergency exception requires VP Engineering and Security Officer dual-key signature.",
            "Deploy to isolated staging environment only with 100% canary traffic monitoring.",
        ]

    elif action == "approve_production_release":
        projected_changes.append({
            "operation": "UPDATE_PROPERTY",
            "entity_id": target_id,
            "property": "status",
            "from_value": t_status,
            "to_value": "approved_for_deployment",
        })
        projected_changes.append({
            "operation": "TRIGGER_WORKFLOW",
            "target_system": "deployment_pipeline",
            "action": "deploy_to_production",
        })
        reversible = False
        risk_level = "LOW" if policy_result.get("allowed") else "CRITICAL"
        mitigation_steps = [
            "Verify all automated smoke tests in staging.",
            "Ensure on-call payment engineers are active before triggering rollout.",
            "Configure automatic rollback trigger upon HTTP 5xx error threshold > 0.1%.",
        ]

    else:
        projected_changes.append({
            "operation": "GENERIC_INTERVENTION",
            "entity_id": target_id,
            "action": action,
            "parameters": params,
        })
        reversible = True
        risk_level = "MEDIUM"
        mitigation_steps = ["Verify preconditions and review audit logs before applying."]

    return {
        "action": action,
        "target_entity": {"id": t_id, "name": t_name, "kind": t_kind, "current_status": t_status},
        "simulation_mode": "counterfactual_dry_run",
        "policy_evaluation": policy_result,
        "projected_state_diff": {
            "modifications_count": len(projected_changes),
            "changes": projected_changes,
        },
        "projected_unblocked_entities": unblocked_entities,
        "blast_radius_summary": impact_result.get("blast_radius", {}),
        "risk_assessment": {
            "risk_level": risk_level,
            "is_reversible": reversible,
            "allowed_under_current_policy": policy_result.get("allowed", False),
        },
        "recommended_mitigations": mitigation_steps,
        "counterfactual_verdict": (
            f"Candidate action '{action}' on '{t_name}' is {risk_level} risk (reversible: {reversible}). "
            f"Policy check: {'PASSED' if policy_result.get('allowed') else 'FAILED'}. "
            f"{'Safe to propose with mitigations.' if policy_result.get('allowed') else 'Violates policy constraints; cannot proceed without resolution.'}"
        ),
    }


def evaluate_candidate_actions(
    candidate_actions: list[dict[str, Any]],
    target_entity_id: str = "",
    tenant_graph: str = "",
) -> dict[str, Any]:
    """
    Compare multiple candidate actions side-by-side against graph evidence and policy constraints,
    producing an explainable comparison matrix and rank-ordered recommendation.
    """
    if not candidate_actions:
        raise ValueError("candidate_actions list must contain at least one action specification")

    evaluated: list[dict[str, Any]] = []

    for idx, cand in enumerate(candidate_actions, start=1):
        action_name = cand.get("action", "").strip()
        tid = (cand.get("target_id") or target_entity_id).strip()
        params = cand.get("params") or {}

        if not action_name or not tid:
            evaluated.append({
                "candidate_index": idx,
                "action": action_name or "UNSPECIFIED",
                "target_id": tid or "UNSPECIFIED",
                "simulated": False,
                "policy_allowed": False,
                "error": "Missing required 'action' or 'target_id'",
                "ranking_score": 0,
            })
            continue

        sim = simulate_candidate_action(action=action_name, target_id=tid, params=params, graph_name=tenant_graph)

        policy_info = sim.get("policy_evaluation", {})
        allowed = policy_info.get("allowed", False)
        verdict = policy_info.get("verdict", "UNRESOLVED")
        risk_level = sim.get("risk_assessment", {}).get("risk_level", "MEDIUM")
        reversible = sim.get("risk_assessment", {}).get("is_reversible", True)
        unblocked_count = len(sim.get("projected_unblocked_entities", []))

        rejection_reason = None
        if not allowed:
            rejection_reason = policy_info.get("reason") or "Policy check failed."
            violated = policy_info.get("violated_rules")
            if violated:
                rejection_reason += f" Violated: {violated}"

        risk_points = {"LOW": 30, "MEDIUM": 15, "HIGH": 0, "CRITICAL": -50}.get(risk_level, 0)
        score = (100 if allowed else 0) + risk_points + (15 if reversible else 0) + (10 * unblocked_count)

        evaluated.append({
            "candidate_index": idx,
            "action": action_name,
            "target_id": tid,
            "target_name": sim.get("target_entity", {}).get("name", tid),
            "policy_verdict": verdict,
            "policy_allowed": allowed,
            "rejection_reason": rejection_reason,
            "risk_level": risk_level,
            "is_reversible": reversible,
            "unblocked_entities_count": unblocked_count,
            "required_approval_role": "vp_engineering" if not allowed else "engineering_lead",
            "ranking_score": score,
            "recommended_mitigations": sim.get("recommended_mitigations", []),
            "counterfactual_verdict": sim.get("counterfactual_verdict", ""),
        })

    evaluated.sort(key=lambda c: c["ranking_score"], reverse=True)

    recommended = evaluated[0] if evaluated else None
    has_viable_option = any(c["policy_allowed"] for c in evaluated)

    return {
        "total_candidates_evaluated": len(evaluated),
        "has_viable_allowed_candidate": has_viable_option,
        "recommended_candidate": (
            {
                "action": recommended["action"],
                "target_id": recommended["target_id"],
                "target_name": recommended["target_name"],
                "policy_allowed": recommended["policy_allowed"],
                "risk_level": recommended["risk_level"],
                "justification": (
                    f"Action '{recommended['action']}' is permitted under governance policy, operates at {recommended['risk_level']} risk, "
                    f"and unblocks {recommended['unblocked_entities_count']} downstream entity(ies)."
                    if recommended["policy_allowed"]
                    else f"No candidate actions were permitted by policy. Best fallback '{recommended['action']}' requires leadership exception."
                ),
            }
            if recommended
            else None
        ),
        "comparison_matrix": evaluated,
        "tenant_graph": tenant_graph or "default",
    }
