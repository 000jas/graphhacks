from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from agent.config import AgentSettings
from agent.models import (
    ActionLifecycleRecord,
    ActionLifecycleStage,
    ActionRiskLevel,
    ActionValidationResult,
    AgentResult,
)
from agent.supervisor import ActionSupervisor, ActionSupervisorError
from mcp_server.decision_memory import (
    propose_action,
    execute_approved_action,
    validate_action_outcome,
    get_action_audit_trail,
)


def test_action_lifecycle_models_and_stage_transitions():
    """Verify ActionLifecycleRecord properly tracks stages, risk level, and history."""
    record = ActionLifecycleRecord(
        lifecycle_id="lc-test-01",
        current_stage=ActionLifecycleStage.DETECT,
        domain="fraud",
        objective="Investigate mule account acc-101",
        action_type="FREEZE_ACCOUNT",
        target_id="acc-101",
    )
    assert record.current_stage == ActionLifecycleStage.DETECT
    assert record.risk_level == ActionRiskLevel.MEDIUM
    assert record.requires_human_approval is True

    record.record_stage(ActionLifecycleStage.PLAN, "Plan formulated for target acc-101")
    assert record.current_stage == ActionLifecycleStage.PLAN
    assert len(record.stage_history) == 1
    assert record.stage_history[0]["stage"] == "plan"

    d = record.to_dict()
    assert d["current_stage"] == "plan"
    assert d["domain"] == "fraud"


def test_supervisor_detect_domain_classification():
    """Verify domain detection across fraud, security, database integrity, and code."""
    settings = AgentSettings(graph_name="test_graph")
    supervisor = ActionSupervisor(settings=settings)

    r_fraud = supervisor.detect("Analyze suspicious transaction velocity on mule wallet")
    assert r_fraud.domain == "fraud"

    r_sec = supervisor.detect("Investigate CVE-2026-9901 remote code execution in auth service")
    assert r_sec.domain == "security"

    r_db = supervisor.detect("Reconcile duplicate person identity records across bank branches")
    assert r_db.domain == "database_integrity"

    r_code = supervisor.detect("Review PR merge conflict and reassign pull request review")
    assert r_code.domain == "codebase"


def test_supervisor_consequential_action_approval_enforcement():
    """Verify consequential actions require human approval and refuse execution without a token."""
    settings = AgentSettings(graph_name="swiftpay_unified")
    supervisor = ActionSupervisor(settings=settings)

    record = ActionLifecycleRecord(
        lifecycle_id="lc-safety-01",
        current_stage=ActionLifecycleStage.VERIFY,
        domain="security",
        objective="Revoke admin access on compromised host",
        action_type="REVOKE_ACCESS",
        target_id="svc-auth",
        requires_human_approval=True,
        proposal_id="prop-test-123",
        approval_token="token-apprv-secret123",
    )

    # Empty approval token must be rejected
    with pytest.raises(ActionSupervisorError, match="requires explicit human approval token"):
        supervisor.execute(record, approval_token="")

    # Blocked by policy token must be rejected
    with pytest.raises(ActionSupervisorError, match="permanently blocked by security/governance policy"):
        supervisor.execute(record, approval_token="BLOCKED_BY_POLICY")


@patch("mcp_server.decision_memory.execute_ro_query")
def test_validation_fails_when_target_missing(mock_ro):
    """Never claim success if target entity does not exist in the graph post-execution."""
    mock_ro.return_value = []  # Entity not found in graph!

    val = validate_action_outcome(
        action="QUARANTINE_NODE",
        target_id="ghost-node-404",
        params={"new_status": "quarantined"},
        graph_name="test_graph",
    )
    assert val["validated"] is False
    assert "not found" in val["error"].lower()
    assert len(val["discrepancies"]) > 0


@patch("mcp_server.decision_memory.execute_ro_query")
def test_validation_fails_on_property_mismatch(mock_ro):
    """Never claim success if post-execution state does not match expected properties."""
    # Target exists, but status is still 'active', NOT 'quarantined'
    mock_ro.return_value = [
        ("node-1", "active", {"id": "node-1", "status": "active"}, ["Entity"])
    ]

    val = validate_action_outcome(
        action="QUARANTINE_NODE",
        target_id="node-1",
        params={"new_status": "quarantined"},
        graph_name="test_graph",
    )
    assert val["validated"] is False
    assert any("Expected status='quarantined', found status='active'" in d for d in val["discrepancies"])


@patch("mcp_server.decision_memory.execute_ro_query")
def test_validation_succeeds_when_ground_truth_matches(mock_ro):
    """Certify success only when the read query confirms the updated state."""
    mock_ro.return_value = [
        ("node-1", "quarantined", {"id": "node-1", "status": "quarantined"}, ["Entity"])
    ]

    val = validate_action_outcome(
        action="QUARANTINE_NODE",
        target_id="node-1",
        params={"new_status": "quarantined"},
        graph_name="test_graph",
    )
    assert val["validated"] is True
    assert "status=quarantined" in val["verified_properties"]
    assert len(val["discrepancies"]) == 0


@patch("mcp_server.decision_memory.execute_rw_query")
@patch("mcp_server.decision_memory.execute_ro_query")
def test_execute_approved_action_blocks_unauthorized_token(mock_ro, mock_rw):
    """Enforce authorization token check."""
    mock_ro.return_value = [
        ("prop-1", "FREEZE_ACCOUNT", "acc-88", "APPROVED_PENDING_EXECUTION", "token-valid-99", {})
    ]

    result = execute_approved_action(
        proposal_id="prop-1",
        approval_token="token-forged-00",
        graph_name="test_graph",
    )
    assert result["executed"] is False
    assert result["status"] == "UNAUTHORIZED"
    mock_rw.assert_not_called()


@patch("mcp_server.decision_memory.execute_rw_query")
@patch("mcp_server.decision_memory.execute_ro_query")
def test_execute_approved_action_full_lifecycle_with_validation(mock_ro, mock_rw):
    """Verify execution triggers post-state verification query and creates verified AuditRecord."""
    # First call: proposal lookup
    # Second call: post-execution read verification query
    mock_ro.side_effect = [
        [("prop-1", "FREEZE_ACCOUNT", "acc-88", "APPROVED_PENDING_EXECUTION", "token-valid-99", {"params": "{}"})],
        [("acc-88", "quarantined", {"id": "acc-88", "status": "quarantined"}, ["Account"])],
    ]

    result = execute_approved_action(
        proposal_id="prop-1",
        approval_token="token-valid-99",
        graph_name="test_graph",
    )

    assert result["executed"] is True
    assert result["validated"] is True
    assert result["status"] == "SUCCESS"
    assert "audit_trail_id" in result
    assert result["validation"]["validated"] is True


@patch("mcp_server.decision_memory.execute_rw_query")
@patch("mcp_server.decision_memory.execute_ro_query")
def test_execute_approved_action_refuses_success_if_validation_fails(mock_ro, mock_rw):
    """If post-state read check fails, mark FAILED_VALIDATION and never claim success."""
    # Proposal found, but post-read check returns status='active' instead of 'quarantined'
    mock_ro.side_effect = [
        [("prop-1", "FREEZE_ACCOUNT", "acc-88", "APPROVED_PENDING_EXECUTION", "token-valid-99", {"params": "{}"})],
        [("acc-88", "active", {"id": "acc-88", "status": "active"}, ["Account"])],
    ]

    result = execute_approved_action(
        proposal_id="prop-1",
        approval_token="token-valid-99",
        graph_name="test_graph",
    )

    assert result["executed"] is False
    assert result["validated"] is False
    assert result["status"] == "FAILED_VALIDATION"
    assert "cannot be claimed" in result["message"].lower()


@patch("agent.supervisor.propose_action")
@patch("agent.supervisor.simulate_candidate_action")
@patch("agent.supervisor.check_action_policy")
def test_supervisor_plan_phase_stops_at_approval_request(mock_policy, mock_sim, mock_prop):
    """Verify plan phase runs Detect -> Investigate -> Plan -> Verify -> Request Approval and halts."""
    mock_sim.return_value = {
        "risk_assessment": {"risk_level": "HIGH"},
        "blast_radius_summary": {"affected_count": 3},
        "counterfactual_verdict": "Requires containment",
    }
    mock_policy.return_value = {"allowed": True, "verdict": "PERMITTED"}
    mock_prop.return_value = {
        "proposal_id": "prop-auto-01",
        "approval_token": "token-test-xyz",
        "policy_allowed": True,
        "status": "APPROVED_PENDING_EXECUTION",
    }

    settings = AgentSettings(graph_name="test_graph")
    supervisor = ActionSupervisor(settings=settings)

    # Fake investigation without executing LLM
    record = ActionLifecycleRecord(
        lifecycle_id="lc-run-01",
        current_stage=ActionLifecycleStage.DETECT,
        domain="fraud",
        objective="Quarantine compromised account acc-77",
        action_type="QUARANTINE_NODE",
        target_id="acc-77",
    )
    record = supervisor.plan(record)
    record = supervisor.verify(record)
    record = supervisor.request_approval(record)

    assert record.current_stage == ActionLifecycleStage.REQUEST_APPROVAL
    assert record.proposal_id == "prop-auto-01"
    assert record.approval_token == "token-test-xyz"
    assert record.requires_human_approval is True
    assert record.executed is False


from starlette.testclient import TestClient
from agent.api import app


def test_api_validate_action_endpoint():
    """Verify /api/actions/validate endpoint checks ground-truth state."""
    client = TestClient(app)
    with patch("mcp_server.decision_memory.execute_ro_query") as mock_ro:
        mock_ro.return_value = [
            ("acc-99", "quarantined", {"id": "acc-99", "status": "quarantined"}, ["Account"])
        ]
        resp = client.post(
            "/api/actions/validate",
            json={
                "action_type": "QUARANTINE_NODE",
                "target_id": "acc-99",
                "params": {"new_status": "quarantined"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["validation"]["validated"] is True
        assert "status=quarantined" in data["validation"]["verified_properties"]


def test_api_audit_trail_endpoint():
    """Verify /api/actions/audit-trail endpoint returns durable records."""
    client = TestClient(app)
    with patch("mcp_server.decision_memory.execute_ro_query") as mock_ro:
        mock_ro.return_value = [
            ("audit-exec-123", "Audit: Freeze", "exec-123", "prop-123", "FREEZE_ACCOUNT", "acc-99", "2026-10-19T00:00:00Z", "SUCCESS", {})
        ]
        resp = client.get("/api/actions/audit-trail?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["records"][0]["status"] == "SUCCESS"


def test_api_remediation_approve_with_ground_truth_verification():
    """Verify /api/remediation/approve executes with ground-truth verification."""
    client = TestClient(app)
    with patch("mcp_server.decision_memory.propose_action") as mock_prop, \
         patch("mcp_server.decision_memory.execute_approved_action") as mock_exec:
        mock_prop.return_value = {
            "proposal_id": "prop-rem-1",
            "approval_token": "token-valid-rem",
            "status": "APPROVED_PENDING_EXECUTION",
        }
        mock_exec.return_value = {
            "executed": True,
            "validated": True,
            "status": "SUCCESS",
            "audit_trail_id": "audit-exec-rem",
            "validation": {"validated": True, "verified_properties": ["status=quarantined"]},
        }

        resp = client.post(
            "/api/remediation/approve",
            json={
                "action_type": "QUARANTINE_NODE",
                "target_id": "acc-compromised-1",
                "rationale": "High-risk mule cluster detected",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["executed"] is True
        assert data["validated"] is True
        assert data["audit_trail_id"] == "audit-exec-rem"


@patch("mcp_server.decision_memory.execute_rw_query")
@patch("mcp_server.decision_memory.execute_ro_query")
def test_cross_domain_security_and_database_integrity_actions(mock_ro, mock_rw):
    """Verify cross-domain actions: REVOKE_ACCESS and MERGE_DUPLICATES."""
    # 1. Test REVOKE_ACCESS: proposal lookup -> entity lookup -> edge lookup (returns empty: edge was deleted)
    mock_ro.side_effect = [
        [("prop-sec-1", "REVOKE_ACCESS", "svc-auth", "APPROVED_PENDING_EXECUTION", "tok-1", {"params": '{"rel_type": "ACCESSES", "related_entity_id": "db-primary"}'})],
        [("svc-auth", "revoked", {"id": "svc-auth", "status": "revoked"}, ["Service"])],
        [],  # edge lookup: deleted!
    ]
    res_sec = execute_approved_action(proposal_id="prop-sec-1", approval_token="tok-1")
    assert res_sec["executed"] is True
    assert res_sec["validated"] is True
    assert res_sec["status"] == "SUCCESS"

    # 2. Test MERGE_DUPLICATES: proposal lookup -> entity lookup -> edge lookup (returns MERGED_INTO edge)
    mock_ro.side_effect = [
        [("prop-db-1", "MERGE_DUPLICATES", "p-dup-2032", "APPROVED_PENDING_EXECUTION", "tok-2", {"params": '{"canonical_id": "p-can-2086"}'})],
        [("p-dup-2032", "merged_inactive", {"id": "p-dup-2032", "status": "merged_inactive"}, ["Person"])],
        [("MERGED_INTO",)],  # edge lookup: created!
    ]
    res_db = execute_approved_action(proposal_id="prop-db-1", approval_token="tok-2")
    assert res_db["executed"] is True
    assert res_db["validated"] is True
    assert res_db["status"] == "SUCCESS"
