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
