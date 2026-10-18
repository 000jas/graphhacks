from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ToolCall:
    """Normalized representation of a tool call requested by a language model."""
    id: str
    function_name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.function_name:
            import re
            self.function_name = re.sub(r"<\|.*?\|>.*", "", self.function_name).strip()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ToolDefinition:
    """Normalized schema representation of an available MCP tool."""
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI / NVIDIA compatible function definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters or {"type": "object", "properties": {}},
            },
        }

    def to_anthropic_schema(self) -> dict[str, Any]:
        """Convert to Anthropic tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters or {"type": "object", "properties": {}},
        }


@dataclass
class ChatMessage:
    """Normalized chat message passed across provider boundaries."""
    role: str
    content: Optional[str] = None
    tool_calls: Optional[list[ToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            res["content"] = self.content
        if self.tool_calls:
            res["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function_name,
                        "arguments": json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else str(tc.arguments),
                    },
                }
                for tc in self.tool_calls
            ]
        if self.tool_call_id:
            res["tool_call_id"] = self.tool_call_id
        if self.name:
            res["name"] = self.name
        return res


@dataclass
class ProviderResponse:
    """Normalized response returned by any LLM provider adapter."""
    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    raw_response: Any = None


@dataclass
class AgentStep:
    """Trace record of a single iteration step in the agent investigation loop."""
    iteration: int
    thought: Optional[str]
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentResult:
    """Final grounded output delivered by the GraphOS Investigator."""
    objective: str
    success: bool
    final_answer: str
    evidence_summary: dict[str, Any]
    steps: list[AgentStep] = field(default_factory=list)
    total_iterations: int = 0
    total_tool_calls: int = 0
    duration_seconds: float = 0.0
    provider_info: dict[str, Any] = field(default_factory=dict)
    unresolved_questions: list[str] = field(default_factory=list)
    completed_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InvestigationEvent:
    """Real-time event emitted during graph investigation for UI streaming."""
    event_type: str
    iteration: int
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ActionLifecycleStage(str, Enum):
    """The 8 explicit stages of the GraphOS Action Lifecycle."""
    DETECT = "detect"
    INVESTIGATE = "investigate"
    PLAN = "plan"
    VERIFY = "verify"
    REQUEST_APPROVAL = "request_approval"
    EXECUTE = "execute"
    VALIDATE = "validate"
    AUDIT = "audit"


class ActionRiskLevel(str, Enum):
    """Risk classification evaluated during the Verify stage."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class ActionValidationResult:
    """Post-execution ground-truth verification result."""
    validated: bool
    target_id: str
    expected_state: dict[str, Any] = field(default_factory=dict)
    actual_state: dict[str, Any] = field(default_factory=dict)
    verified_properties: list[str] = field(default_factory=list)
    discrepancies: list[str] = field(default_factory=list)
    verified_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ActionLifecycleRecord:
    """End-to-end trace of an action across the full lifecycle."""
    lifecycle_id: str
    current_stage: ActionLifecycleStage
    domain: str
    objective: str
    action_type: str
    target_id: str
    params: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    risk_level: ActionRiskLevel = ActionRiskLevel.MEDIUM
    is_consequential: bool = True
    requires_human_approval: bool = True
    proposal_id: Optional[str] = None
    approval_token: Optional[str] = None
    is_approved: bool = False
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    execution_id: Optional[str] = None
    executed: bool = False
    executed_at: Optional[str] = None
    validation: Optional[ActionValidationResult] = None
    post_state_verified: bool = False
    audit_record_id: Optional[str] = None
    stage_history: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def record_stage(self, stage: ActionLifecycleStage, message: str, data: Optional[dict[str, Any]] = None) -> None:
        self.current_stage = stage
        self.stage_history.append({
            "stage": stage.value,
            "message": message,
            "data": data or {},
            "timestamp": utc_now_iso(),
        })

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["current_stage"] = self.current_stage.value
        d["risk_level"] = self.risk_level.value
        return d
