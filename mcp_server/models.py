from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class EvidenceClassification(str, Enum):
    FACT = "FACT"
    DERIVED = "DERIVED"
    INFERENCE = "INFERENCE"
    GAP = "GAP"
    CONFLICT = "CONFLICT"


class PolicyVerdict(str, Enum):
    PERMITTED = "PERMITTED"
    REJECTED = "REJECTED"
    UNRESOLVED = "UNRESOLVED"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EntityNode:
    id: str
    name: str
    kind: str
    status: Optional[str] = None
    properties: dict[str, Any] = field(default_factory=dict)
    source_ref: Optional[str] = None


@dataclass
class EdgeEvidence:
    type: str
    from_id: str
    to_id: str
    source_record_id: Optional[str] = None
    observed_at: Optional[str] = None
    confidence: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidencePath:
    depth: int
    nodes: list[EntityNode]
    edges: list[EdgeEvidence]
    classification: EvidenceClassification = EvidenceClassification.DERIVED


@dataclass
class PolicyEvaluation:
    action: str
    target_id: str
    verdict: PolicyVerdict
    reason: str
    governing_policies: list[dict[str, Any]] = field(default_factory=list)
    missing_prerequisites: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class SimulationResult:
    action: str
    target_id: str
    params: dict[str, Any]
    projected_changes: list[dict[str, Any]]
    policy_verdict: PolicyVerdict
    policy_reason: str
    blast_radius_impact: dict[str, Any]
    risk_level: str
    reversible: bool
    mitigation_steps: list[str]
    simulated_at: str = field(default_factory=utc_now)


@dataclass
class ActionProposal:
    proposal_id: str
    action: str
    target_id: str
    rationale: str
    evidence_ids: list[str]
    params: dict[str, Any]
    status: str
    policy_verdict: PolicyVerdict
    created_at: str = field(default_factory=utc_now)
    required_approval_role: str = "engineering_lead"


@dataclass
class ExecutionRecord:
    execution_id: str
    proposal_id: str
    action: str
    target_id: str
    status: str
    applied_changes: list[dict[str, Any]]
    executed_at: str = field(default_factory=utc_now)
    audit_trail_id: str = ""


@dataclass
class DecisionMemory:
    memory_id: str
    finding_id: str
    target_entity_ids: list[str]
    summary: str
    outcome_status: str
    evidence_refs: list[str]
    variance_analysis: str
    recorded_at: str = field(default_factory=utc_now)


@dataclass
class InvestigationFinding:
    finding_id: str
    title: str
    objective: str
    key_findings: list[str]
    supporting_entity_ids: list[str]
    evidence_path_ids: list[str] = field(default_factory=list)
    confidence: str = "HIGH"
    status: str = "ACTIVE"
    created_at: str = field(default_factory=utc_now)
    superseded_by: Optional[str] = None
    superseded_reason: Optional[str] = None


@dataclass
class EvidenceQualityReport:
    entity_id: Optional[str]
    scope: str
    total_edges_inspected: int
    verified_edges_count: int
    verification_rate: float
    average_confidence: float
    freshness_score: float
    stale_relationships_count: int
    unverified_edges: list[dict[str, Any]]
    quality_rating: str
    evaluated_at: str = field(default_factory=utc_now)
    limitations: list[str] = field(default_factory=list)


@dataclass
class SchemaSummary:
    tenant_graph: str
    total_nodes: int
    total_edges: int
    density: float
    average_degree: float
    connected_components: int
    node_types: list[dict[str, Any]]
    relationship_types: list[dict[str, Any]]
    property_catalog: dict[str, list[dict[str, Any]]]
    schema_anomalies: list[dict[str, Any]]
    inspected_at: str = field(default_factory=utc_now)


def serialize_json(data: Any) -> str:
    """Format structured responses consistently for MCP clients."""
    if hasattr(data, "__dataclass_fields__"):
        data = asdict(data)
    elif isinstance(data, Enum):
        data = data.value
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)
