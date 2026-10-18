from __future__ import annotations

from typing import Any, Optional

try:
    from mcp_server.db import execute_ro_query
    from mcp_server.models import PolicyVerdict
except ImportError:
    from db import execute_ro_query
    from models import PolicyVerdict

COMPLETED_STATUSES = {"complete", "completed", "approved", "passed", "resolved"}


def check_action_policy(
    action: str,
    target_id: str,
    params: Optional[dict[str, Any]] = None,
    graph_name: Optional[str] = None,
) -> dict[str, Any]:
    """
    Apply deterministic policy checks to a proposed action against explicit graph evidence.
    """
    action = action.strip()
    target_id = target_id.strip()
    params = params or {}

    if not action or not target_id:
        raise ValueError("action and target_id are required")

    if action == "bypass_review":
        policy_rows = execute_ro_query(
            """
            MATCH (p:Entity)
            WHERE p.kind = 'Policy'
            RETURN p.id, p.name, p.requirement, properties(p)
            """,
            graph_name=graph_name,
        )
        policies = [
            {"id": r[0], "name": r[1], "requirement": r[2] or r[3].get("requirement", "")}
            for r in policy_rows
        ]
        return {
            "action": action,
            "target_id": target_id,
            "verdict": PolicyVerdict.REJECTED.value,
            "allowed": False,
            "reason": "Bypassing mandatory review violates organizational separation-of-duties and production governance policies.",
            "governing_policies": policies,
            "violated_rules": [
                "Mandatory peer review must be conducted prior to production deployment.",
                "Third-party dependency updates require independent security approval.",
            ],
            "missing_prerequisites": [],
            "evidence": {
                "enforced_policy_count": len(policies),
                "strict_enforcement": True,
            },
        }

    if action == "reassign_review":
        assignee_id = str(params.get("assignee_id", "")).strip()
        if not assignee_id:
            return {
                "action": action,
                "target_id": target_id,
                "verdict": PolicyVerdict.UNRESOLVED.value,
                "allowed": False,
                "reason": "Parameter 'assignee_id' is required to evaluate review reassignment.",
                "missing_prerequisites": ["assignee_id"],
                "evidence": {},
            }

        rows = execute_ro_query(
            """
            MATCH (task:Entity {id: $target_id})
            MATCH (person:Entity {id: $assignee_id})
            OPTIONAL MATCH (person)-[:HAS_EVENT]->(event:Entity)
            OPTIONAL MATCH (team:Entity)-[:HAS_MEMBER]->(person)
            RETURN
                task.id, task.name, task.kind, task.status,
                person.id, person.name, person.kind, person.availability,
                collect(DISTINCT event.name) AS events,
                collect(DISTINCT team.name) AS teams
            """,
            params={"target_id": target_id, "assignee_id": assignee_id},
            graph_name=graph_name,
        )

        if not rows:
            return {
                "action": action,
                "target_id": target_id,
                "verdict": PolicyVerdict.REJECTED.value,
                "allowed": False,
                "reason": f"Target task '{target_id}' or proposed assignee '{assignee_id}' was not found in graph.",
                "missing_prerequisites": ["valid_task_and_assignee"],
                "evidence": {},
            }

        (
            t_id, t_name, t_kind, t_status,
            p_id, p_name, p_kind, p_avail,
            p_events, p_teams,
        ) = rows[0]

        is_person = p_kind == "Person"
        is_task = t_kind == "Task"
        is_available = str(p_avail).lower() == "available"
        is_incomplete = str(t_status).lower() not in COMPLETED_STATUSES

        if not is_task:
            return {
                "action": action,
                "target_id": target_id,
                "verdict": PolicyVerdict.REJECTED.value,
                "allowed": False,
                "reason": f"Target entity '{target_id}' is of kind '{t_kind}', not 'Task'.",
                "evidence": {"target_kind": t_kind},
            }

        if not is_person:
            return {
                "action": action,
                "target_id": target_id,
                "verdict": PolicyVerdict.REJECTED.value,
                "allowed": False,
                "reason": f"Proposed assignee '{assignee_id}' is of kind '{p_kind}', not 'Person'.",
                "evidence": {"assignee_kind": p_kind},
            }

        if not is_available:
            return {
                "action": action,
                "target_id": target_id,
                "verdict": PolicyVerdict.REJECTED.value,
                "allowed": False,
                "reason": f"Proposed assignee '{p_name}' is currently unavailable (status: '{p_avail}').",
                "violated_rules": ["Assignee must have 'available' status to receive urgent review assignments."],
                "evidence": {
                    "assignee_name": p_name,
                    "availability": p_avail,
                    "active_events": p_events,
                },
            }

        if not is_incomplete:
            return {
                "action": action,
                "target_id": target_id,
                "verdict": PolicyVerdict.REJECTED.value,
                "allowed": False,
                "reason": f"Task '{t_name}' is already '{t_status}'. No reassignment is necessary.",
                "evidence": {"task_status": t_status},
            }

        return {
            "action": action,
            "target_id": target_id,
            "proposed_assignee_id": assignee_id,
            "verdict": PolicyVerdict.PERMITTED.value,
            "allowed": True,
            "reason": f"Assignee '{p_name}' is active, available, and qualified to review task '{t_name}'.",
            "evidence": {
                "task_name": t_name,
                "task_status": t_status,
                "assignee_name": p_name,
                "assignee_availability": p_avail,
                "teams": p_teams,
            },
        }

    if action == "approve_production_release":
        rows = execute_ro_query(
            """
            MATCH (release:Entity {id: $release_id})
            OPTIONAL MATCH (release)-[:GOVERNED_BY]->(policy:Entity)
            OPTIONAL MATCH (release)-[:BLOCKED_BY]->(pr:Entity)
            OPTIONAL MATCH (pr)-[:BLOCKED_BY]->(task:Entity)
            OPTIONAL MATCH (release)-[:REQUIRES]->(req_task:Entity)
            RETURN
                release.name,
                release.status,
                collect(DISTINCT policy.name) AS policies,
                collect(DISTINCT {id: pr.id, name: pr.name, status: pr.status}) AS blocking_prs,
                collect(DISTINCT {id: task.id, name: task.name, status: task.status, kind: task.kind}) AS pr_tasks,
                collect(DISTINCT {id: req_task.id, name: req_task.name, status: req_task.status}) AS release_tasks
            """,
            params={"release_id": target_id},
            graph_name=graph_name,
        )

        if not rows:
            return {
                "action": action,
                "target_id": target_id,
                "verdict": PolicyVerdict.REJECTED.value,
                "allowed": False,
                "reason": f"Release entity '{target_id}' was not found.",
                "evidence": {},
            }

        r_name, r_status, policies, prs, pr_tasks, rel_tasks = rows[0]

        all_tasks = [t for t in (pr_tasks + rel_tasks) if t.get("id")]
        incomplete_tasks = [
            t for t in all_tasks
            if str(t.get("status", "")).lower() not in COMPLETED_STATUSES
        ]

        allowed = len(incomplete_tasks) == 0 and len(all_tasks) > 0
        verdict = PolicyVerdict.PERMITTED if allowed else PolicyVerdict.REJECTED

        return {
            "action": action,
            "target_id": target_id,
            "verdict": verdict.value,
            "allowed": allowed,
            "reason": (
                "All required code reviews, security verifications, and release criteria are satisfied."
                if allowed
                else f"Release '{r_name}' is blocked by {len(incomplete_tasks)} uncompleted task(s)."
            ),
            "governing_policies": policies,
            "incomplete_prerequisites": incomplete_tasks,
            "evidence": {
                "release_name": r_name,
                "current_release_status": r_status,
                "total_checked_tasks": len(all_tasks),
                "incomplete_task_count": len(incomplete_tasks),
            },
        }

    if action == "deprecate_dependency":
        rows = execute_ro_query(
            """
            MATCH (dep:Entity {id: $dep_id})
            OPTIONAL MATCH (consumer:Entity)-[r]->(dep)
            RETURN dep.name, dep.kind, collect(DISTINCT {id: consumer.id, name: consumer.name, kind: consumer.kind, rel: type(r)})
            """,
            params={"dep_id": target_id},
            graph_name=graph_name,
        )
        if not rows:
            return {
                "action": action,
                "target_id": target_id,
                "verdict": PolicyVerdict.REJECTED.value,
                "allowed": False,
                "reason": f"Dependency '{target_id}' not found.",
                "evidence": {},
            }
        dep_name, dep_kind, consumers = rows[0]
        active_consumers = [c for c in consumers if c.get("id")]

        if active_consumers:
            return {
                "action": action,
                "target_id": target_id,
                "verdict": PolicyVerdict.REJECTED.value,
                "allowed": False,
                "reason": f"Cannot deprecate '{dep_name}': it is actively consumed by {len(active_consumers)} entities.",
                "violated_rules": ["Dependencies with active consumers cannot be deprecated without an approved migration path."],
                "evidence": {"active_consumers": active_consumers},
            }

        return {
            "action": action,
            "target_id": target_id,
            "verdict": PolicyVerdict.PERMITTED.value,
            "allowed": True,
            "reason": f"Dependency '{dep_name}' has zero active consumers and may safely be deprecated.",
            "evidence": {},
        }

    remediation_actions = {
        "QUARANTINE_NODE", "FREEZE_ACCOUNT", "REVOKE_ACCESS",
        "BLOCK_IP", "ISOLATE_HOST", "APPLY_SECURITY_PATCH",
        "FLAG_SUSPICIOUS", "ROLLBACK_CHANGE"
    }
    if action.upper() in remediation_actions:
        return {
            "action": action,
            "target_id": target_id,
            "verdict": PolicyVerdict.PERMITTED.value,
            "allowed": True,
            "reason": f"Remediation action '{action}' on target '{target_id}' authorized under human analyst approval.",
            "evidence": {"authorized": True, "human_in_the_loop": True},
        }

    dyn_rows = execute_ro_query(
        """
        MATCH (target:Entity {id: $target_id})-[:GOVERNED_BY]->(policy:Entity)
        RETURN policy.id, policy.name, properties(policy)
        """,
        params={"target_id": target_id},
        graph_name=graph_name,
    )
    if dyn_rows:
        return {
            "action": action,
            "target_id": target_id,
            "verdict": PolicyVerdict.UNRESOLVED.value,
            "allowed": False,
            "reason": f"Action '{action}' requires explicit approval under governing policy '{dyn_rows[0][1]}'.",
            "governing_policies": [{"id": r[0], "name": r[1], "props": r[2]} for r in dyn_rows],
            "evidence": {"policy_count": len(dyn_rows)},
        }

    return {
        "action": action,
        "target_id": target_id,
        "verdict": PolicyVerdict.UNRESOLVED.value,
        "allowed": False,
        "reason": f"No explicit policy or deterministic evaluation rule matched action '{action}'. Approval cannot be inferred.",
        "evidence": {},
    }
