from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Callable, Optional

from agent.config import AgentSettings, settings as default_settings
from agent.engine import GraphOSInvestigator
from agent.models import (
    ActionLifecycleRecord,
    ActionLifecycleStage,
    ActionRiskLevel,
    ActionValidationResult,
    AgentResult,
)
from mcp_server.counterfactual import simulate_candidate_action
from mcp_server.decision_memory import (
    execute_approved_action,
    get_action_audit_trail,
    propose_action,
    validate_action_outcome,
)
from mcp_server.policy import check_action_policy

logger = logging.getLogger("graphos.agent.supervisor")

SYSTEM_GRAPHS = {"graphos_auth", "system", "admin", "config"}


class ActionSupervisorError(Exception):
    """Raised when an action lifecycle policy or permission is violated."""


class ActionSupervisor:
    """
    Supervisor Agent coordinating the complete 8-stage Action Lifecycle:
    Detect -> Investigate -> Plan -> Verify -> Request Approval -> Execute -> Validate -> Audit.
    
    Enforces safety policies, permission boundaries, and explicit human approvals.
    Ensures actions are schema-aware and domain-independent.
    Strictly verifies outcomes against graph state before certifying success.
    """

    def __init__(
        self,
        settings: Optional[AgentSettings] = None,
        investigator: Optional[GraphOSInvestigator] = None,
    ) -> None:
        self.settings = settings or default_settings
        self.investigator = investigator or GraphOSInvestigator(settings=self.settings)

    def _is_system_graph(self, graph_name: Optional[str]) -> bool:
        if not graph_name:
            return False
        clean = graph_name.strip().lower()
        return clean in SYSTEM_GRAPHS or clean.startswith(("sys_", "admin_"))

    def detect(
        self,
        objective: str,
        context: Optional[dict[str, Any]] = None,
        domain: Optional[str] = None,
    ) -> ActionLifecycleRecord:
        """
        Stage 1: DETECT
        Identify issues, anomalies, integrity gaps, or user objectives.
        Classify domain and initialize the lifecycle trace.
        """
        objective = (objective or "").strip()
        context = context or {}
        lifecycle_id = f"act-lc-{uuid.uuid4().hex[:10]}"

        # Infer domain from objective and context keywords
        inferred_domain = domain or context.get("domain")
        if not inferred_domain:
            low_obj = objective.lower()
            if any(k in low_obj for k in ("cve", "vulnerability", "rce", "iam", "exploit", "cwe", "security", "firewall")):
                inferred_domain = "security"
            elif any(k in low_obj for k in ("fraud", "mule", "launder", "velocity", "transaction", "balance", "wallet", "swiftpay")):
                inferred_domain = "fraud"
            elif any(k in low_obj for k in ("duplicate", "integrity", "reconcile", "unify", "person")):
                inferred_domain = "database_integrity"
            elif any(k in low_obj for k in ("code", "commit", "pull request", "pr ", " pr", "repo", "ast", "branch", "review", "merge conflict")):
                inferred_domain = "codebase"
            else:
                inferred_domain = "general"

        target_id = context.get("target_id", "")
        action_type = context.get("action_type", "")

        record = ActionLifecycleRecord(
            lifecycle_id=lifecycle_id,
            current_stage=ActionLifecycleStage.DETECT,
            domain=inferred_domain,
            objective=objective,
            action_type=action_type,
            target_id=target_id,
            params=context.get("params", {}),
            rationale=context.get("rationale", ""),
            metadata={"context": context},
        )
        record.record_stage(
            ActionLifecycleStage.DETECT,
            f"Detected issue/objective in domain '{inferred_domain}': {objective[:120]}...",
            {"domain": inferred_domain, "initial_target": target_id},
        )
        return record

    async def investigate(
        self,
        record: ActionLifecycleRecord,
        on_step_callback: Optional[Callable] = None,
        on_event_callback: Optional[Callable] = None,
        tenant_graph: Optional[str] = None,
    ) -> ActionLifecycleRecord:
        """
        Stage 2: INVESTIGATE
        Execute deep root-cause analysis and multi-hop graph exploration
        using the read-only GraphOSInvestigator.
        """
        record.record_stage(
            ActionLifecycleStage.INVESTIGATE,
            f"Initiating evidence-bound graph investigation for objective: {record.objective}",
        )
        target_graph = tenant_graph or self.settings.graph_name

        agent_result: AgentResult = await self.investigator.investigate(
            objective=record.objective,
            on_step_callback=on_step_callback,
            on_event_callback=on_event_callback,
        )

        record.metadata["investigation_result"] = agent_result.to_dict()
        record.metadata["evidence_summary"] = agent_result.evidence_summary
        record.metadata["final_answer"] = agent_result.final_answer

        # If target_id wasn't set, try extracting from investigation focal entities
        if not record.target_id:
            entities = agent_result.evidence_summary.get("entities", {})
            if entities:
                # Select first focal entity
                record.target_id = next(iter(entities.keys()))

        record.record_stage(
            ActionLifecycleStage.INVESTIGATE,
            f"Investigation concluded with {len(agent_result.evidence_summary.get('entities', {}))} verified entities and {len(agent_result.steps)} steps.",
            {"entities_count": len(agent_result.evidence_summary.get("entities", {}))},
        )
        return record

    def plan(
        self,
        record: ActionLifecycleRecord,
        action_type: Optional[str] = None,
        target_id: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
        rationale: Optional[str] = None,
        tenant_graph: Optional[str] = None,
    ) -> ActionLifecycleRecord:
        """
        Stage 3: PLAN
        Formulate a schema-aware corrective action plan with target entity,
        parameters, and operational justification.
        """
        if action_type:
            record.action_type = action_type.strip()
        if target_id:
            record.target_id = target_id.strip()
        if params is not None:
            record.params = params
        if rationale:
            record.rationale = rationale.strip()

        # If action_type still undefined, attempt to infer from investigation recommendations
        if not record.action_type:
            answer = record.metadata.get("final_answer", "")
            low_ans = answer.lower()
            if "quarantine" in low_ans or "isolate" in low_ans:
                record.action_type = "QUARANTINE_NODE"
            elif "freeze" in low_ans or "block" in low_ans:
                record.action_type = "FREEZE_ACCOUNT"
            elif "revoke" in low_ans or "iam" in low_ans:
                record.action_type = "REVOKE_ACCESS"
            elif "merge" in low_ans or "duplicate" in low_ans:
                record.action_type = "MERGE_DUPLICATES"
            elif "reassign" in low_ans or "review" in low_ans:
                record.action_type = "REASSIGN_TASK"
            else:
                record.action_type = "UPDATE_STATUS"

        if not record.rationale:
            record.rationale = f"Supervisor planned {record.action_type} on target {record.target_id} based on grounded investigation."

        if not record.target_id:
            raise ActionSupervisorError("Cannot plan action: target_id is required but could not be determined.")

        record.record_stage(
            ActionLifecycleStage.PLAN,
            f"Formulated corrective action plan: '{record.action_type}' targeting '{record.target_id}'.",
            {
                "action_type": record.action_type,
                "target_id": record.target_id,
                "params": record.params,
                "rationale": record.rationale,
            },
        )
        return record

    def verify(
        self,
        record: ActionLifecycleRecord,
        tenant_graph: Optional[str] = None,
    ) -> ActionLifecycleRecord:
        """
        Stage 4: VERIFY
        Run counterfactual dry-run simulations, blast radius calculations,
        and policy compliance checks before requesting approval.
        """
        target_graph = tenant_graph or self.settings.graph_name
        if self._is_system_graph(target_graph):
            raise ActionSupervisorError(f"PERMISSION DENIED: Cannot execute actions on protected internal graph '{target_graph}'.")

        # 1. Counterfactual simulation & Blast Radius
        simulation = simulate_candidate_action(
            action=record.action_type,
            target_id=record.target_id,
            params=record.params,
            graph_name=target_graph,
        )
        record.metadata["simulation"] = simulation
        record.metadata["blast_radius"] = simulation.get("blast_radius_summary", {})

        # 2. Policy evaluation
        policy = check_action_policy(
            action=record.action_type,
            target_id=record.target_id,
            params=record.params,
            graph_name=target_graph,
        )
        record.metadata["policy_evaluation"] = policy

        # 3. Determine Risk Level
        risk_str = simulation.get("risk_assessment", {}).get("risk_level", "MEDIUM").upper()
        if risk_str == "CRITICAL":
            record.risk_level = ActionRiskLevel.CRITICAL
        elif risk_str == "HIGH":
            record.risk_level = ActionRiskLevel.HIGH
        elif risk_str == "LOW":
            record.risk_level = ActionRiskLevel.LOW
        else:
            record.risk_level = ActionRiskLevel.MEDIUM

        # 4. Enforce consequential action human approval policy
        # Any state-mutating action or MEDIUM/HIGH/CRITICAL risk requires human supervisor approval
        is_mutating = record.action_type.upper() not in {"SIMULATE", "QUERY", "INSPECT", "READ"}
        record.is_consequential = is_mutating or (record.risk_level in {ActionRiskLevel.MEDIUM, ActionRiskLevel.HIGH, ActionRiskLevel.CRITICAL})
        record.requires_human_approval = record.is_consequential

        allowed = policy.get("allowed", False)
        if not allowed:
            record.record_stage(
                ActionLifecycleStage.VERIFY,
                f"Policy verification REJECTED action '{record.action_type}': {policy.get('reason', 'Policy constraint violated.')}",
                {"policy_verdict": policy.get("verdict"), "allowed": False},
            )
            return record

        record.record_stage(
            ActionLifecycleStage.VERIFY,
            f"Pre-flight verification PASSED. Risk Level: {record.risk_level.value}. Human Approval Required: {record.requires_human_approval}.",
            {
                "risk_level": record.risk_level.value,
                "requires_approval": record.requires_human_approval,
                "blast_radius": record.metadata.get("blast_radius", {}),
            },
        )
        return record

    def request_approval(
        self,
        record: ActionLifecycleRecord,
        tenant_graph: Optional[str] = None,
    ) -> ActionLifecycleRecord:
        """
        Stage 5: REQUEST APPROVAL
        Create formal ActionProposal node in FalkorDB and issue cryptographic approval token.
        Halts consequential actions until human analyst explicitly confirms.
        """
        target_graph = tenant_graph or self.settings.graph_name
        evidence_ids = list(record.metadata.get("evidence_summary", {}).get("entities", {}).keys())[:5]

        proposal = propose_action(
            action=record.action_type,
            target_id=record.target_id,
            rationale=record.rationale,
            evidence_ids=evidence_ids,
            params=record.params,
            graph_name=target_graph,
        )

        record.proposal_id = proposal.get("proposal_id")
        record.approval_token = proposal.get("approval_token")
        record.metadata["proposal"] = proposal

        if not proposal.get("policy_allowed", False):
            record.record_stage(
                ActionLifecycleStage.REQUEST_APPROVAL,
                f"Action proposal was blocked by governing policy: {proposal.get('status')}",
                {"status": proposal.get("status")},
            )
            return record

        if record.requires_human_approval:
            record.record_stage(
                ActionLifecycleStage.REQUEST_APPROVAL,
                f"Action proposal '{record.proposal_id}' created. AWAITING EXPLICIT HUMAN SUPERVISOR APPROVAL (Token: {record.approval_token}).",
                {
                    "proposal_id": record.proposal_id,
                    "approval_token": record.approval_token,
                    "risk_level": record.risk_level.value,
                },
            )
        else:
            # Auto-approved for non-consequential / read verification
            record.is_approved = True
            record.approved_by = "system_supervisor_auto"
            record.record_stage(
                ActionLifecycleStage.REQUEST_APPROVAL,
                f"Action proposal '{record.proposal_id}' auto-approved for non-consequential operation.",
                {"proposal_id": record.proposal_id},
            )

        return record

    def execute(
        self,
        record: ActionLifecycleRecord,
        approval_token: str,
        approved_by: str = "human_supervisor",
        tenant_graph: Optional[str] = None,
    ) -> ActionLifecycleRecord:
        """
        Stage 6: EXECUTE
        Enforce permissions, validate human approval token, and execute authorized mutation.
        """
        target_graph = tenant_graph or self.settings.graph_name
        approval_token = approval_token.strip()

        if not record.proposal_id:
            raise ActionSupervisorError("Cannot execute action without an active proposal_id.")

        # Permission & Safety check
        if record.requires_human_approval and not approval_token:
            raise ActionSupervisorError(
                f"PERMISSION DENIED: Consequential action '{record.action_type}' requires explicit human approval token."
            )

        if approval_token == "BLOCKED_BY_POLICY":
            raise ActionSupervisorError("PERMISSION DENIED: Action is permanently blocked by security/governance policy.")

        exec_res = execute_approved_action(
            proposal_id=record.proposal_id,
            approval_token=approval_token,
            graph_name=target_graph,
        )

        record.is_approved = True
        record.approved_by = approved_by
        record.metadata["execution_response"] = exec_res

        if not exec_res.get("executed", False) and exec_res.get("status") not in {"ALREADY_EXECUTED", "SUCCESS"}:
            msg = exec_res.get("message", "Execution failed")
            record.record_stage(
                ActionLifecycleStage.EXECUTE,
                f"Action execution FAILED: {msg}",
                {"execution_response": exec_res},
            )
            return record

        record.execution_id = exec_res.get("execution_id")
        record.executed = True
        record.executed_at = exec_res.get("executed_at")
        record.audit_record_id = exec_res.get("audit_trail_id")

        record.record_stage(
            ActionLifecycleStage.EXECUTE,
            f"Action '{record.action_type}' executed on '{record.target_id}'. Execution ID: {record.execution_id}.",
            {
                "execution_id": record.execution_id,
                "applied_changes": exec_res.get("applied_changes", []),
            },
        )
        return record

    def validate(
        self,
        record: ActionLifecycleRecord,
        tenant_graph: Optional[str] = None,
    ) -> ActionLifecycleRecord:
        """
        Stage 7: VALIDATE
        Ground-truth post-execution verification: query FalkorDB directly to confirm
        that the expected state changes actually materialized.
        NEVER claim success unless verified!
        """
        target_graph = tenant_graph or self.settings.graph_name

        # If execution already returned an embedded ground-truth validation result, inspect it
        exec_val = record.metadata.get("execution_response", {}).get("validation")
        if not exec_val:
            exec_val = validate_action_outcome(
                action=record.action_type,
                target_id=record.target_id,
                params=record.params,
                graph_name=target_graph,
            )

        val_result = ActionValidationResult(
            validated=exec_val.get("validated", False),
            target_id=record.target_id,
            expected_state=exec_val.get("expected_state", {}),
            actual_state=exec_val.get("actual_state", {}),
            verified_properties=exec_val.get("verified_properties", []),
            discrepancies=exec_val.get("discrepancies", []),
            verified_at=exec_val.get("verified_at", ""),
        )
        record.validation = val_result
        record.post_state_verified = val_result.validated

        if not val_result.validated:
            record.record_stage(
                ActionLifecycleStage.VALIDATE,
                f"POST-EXECUTION VALIDATION FAILED: {', '.join(val_result.discrepancies) or 'State did not match expected outcome.'}",
                {"validation": val_result.to_dict()},
            )
            # Revert executed flag to reflect unverified failure
            record.executed = False
            return record

        record.record_stage(
            ActionLifecycleStage.VALIDATE,
            f"Ground-truth post-state verified in FalkorDB: {', '.join(val_result.verified_properties)}.",
            {"validation": val_result.to_dict()},
        )
        return record

    def audit(
        self,
        record: ActionLifecycleRecord,
        tenant_graph: Optional[str] = None,
    ) -> ActionLifecycleRecord:
        """
        Stage 8: AUDIT
        Confirm permanent, immutable AuditRecord existence in FalkorDB with full provenance.
        """
        target_graph = tenant_graph or self.settings.graph_name
        audit_trail = get_action_audit_trail(
            proposal_id=record.proposal_id or "",
            target_id=record.target_id,
            limit=5,
            graph_name=target_graph,
        )

        record.metadata["audit_trail"] = audit_trail
        records = audit_trail.get("records", [])
        if records:
            record.audit_record_id = records[0].get("id")

        status_str = "SUCCESS" if record.post_state_verified else "FAILED_VALIDATION"
        record.record_stage(
            ActionLifecycleStage.AUDIT,
            f"Immutable audit trail confirmed in graph: Record ID '{record.audit_record_id}'. Final Status: {status_str}.",
            {"audit_record_id": record.audit_record_id, "status": status_str},
        )
        return record

    async def run_plan_phase(
        self,
        objective: str,
        target_id: Optional[str] = None,
        action_type: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
        rationale: Optional[str] = None,
        tenant_graph: Optional[str] = None,
        on_step_callback: Optional[Callable] = None,
        on_event_callback: Optional[Callable] = None,
    ) -> ActionLifecycleRecord:
        """
        Runs Detect -> Investigate -> Plan -> Verify -> Request Approval.
        Stops at Stage 5 awaiting human authorization.
        """
        context = {"target_id": target_id or "", "action_type": action_type or "", "params": params or {}}
        record = self.detect(objective=objective, context=context)
        record = await self.investigate(record, on_step_callback=on_step_callback, on_event_callback=on_event_callback, tenant_graph=tenant_graph)
        record = self.plan(record, action_type=action_type, target_id=target_id, params=params, rationale=rationale, tenant_graph=tenant_graph)
        record = self.verify(record, tenant_graph=tenant_graph)
        record = self.request_approval(record, tenant_graph=tenant_graph)
        return record

    def run_execution_phase(
        self,
        record: ActionLifecycleRecord,
        approval_token: str,
        approved_by: str = "human_supervisor",
        tenant_graph: Optional[str] = None,
    ) -> ActionLifecycleRecord:
        """
        Runs Execute -> Validate -> Audit given an approved proposal and token.
        """
        record = self.execute(record, approval_token=approval_token, approved_by=approved_by, tenant_graph=tenant_graph)
        record = self.validate(record, tenant_graph=tenant_graph)
        record = self.audit(record, tenant_graph=tenant_graph)
        return record
