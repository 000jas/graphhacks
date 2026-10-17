from __future__ import annotations

import logging
import re
from typing import Any, Optional

from agent.config import AgentSettings
from agent.models import ToolCall, ToolDefinition

logger = logging.getLogger("graphos.agent.guardrails")

READ_ONLY_ALLOWED_TOOLS = {
    "search_connected_entities",
    "get_entity_profile",
    "inspect_entity_neighbors",
    "traverse_relationships",
    "find_shortest_evidence_path",
    "run_graph_algorithm",
    "analyze_graph_impact",
    "retrieve_source_documents",
    "check_policy",
    "simulate_action",
    "discover_relationship_patterns",
    "find_common_neighbors",
    "find_alternative_paths",
    "detect_critical_dependencies",
    "detect_communities",
    "detect_graph_anomalies",
    "analyze_reachability",
    "compare_connectivity",
    "search_entities_advanced",
    "compare_entities",
    "investigate_entity_cluster",
    "extract_investigation_subgraph",
    "compare_evidence_paths",
    "batch_get_entities",
    "generate_investigation_summary",
    "discover_graph_schema",
    "evaluate_evidence_quality",
    "detect_conflicting_evidence",
    "inspect_temporal_graph",
    "assess_change_risk_and_impact",
    "evaluate_candidate_actions",
    "query_decision_memory",
    "run_read_only_cypher_query",
}

MUTATING_TOOLS_BLOCKLIST = {
    "propose_action",
    "execute_approved_action",
    "record_outcome",
    "record_investigation_finding",
    "supersede_finding",
}


class GuardrailViolationError(Exception):
    """Raised when a guardrail rule or read-only policy is violated."""


class GuardrailManager:
    """Enforces application-level read-only access, parameter bounds, and anti-loop detection."""

    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings
        self.read_only = settings.read_only
        self.recent_tool_calls: list[tuple[str, str]] = []

    def filter_available_tools(
        self, discovered_tools: list[ToolDefinition]
    ) -> list[ToolDefinition]:
        """
        Filter exposed MCP tools based on read-only permissions and allowlists.
        Mutation tools are completely stripped from the model's exposed toolset.
        """
        permitted: list[ToolDefinition] = []
        for tool in discovered_tools:
            name = tool.name
            if self.read_only:
                if name in MUTATING_TOOLS_BLOCKLIST:
                    logger.debug(f"Guardrail: Stripped mutating tool '{name}' from read-only agent")
                    continue
                if name not in READ_ONLY_ALLOWED_TOOLS:
                    logger.warning(f"Guardrail: Excluding unverified tool '{name}' not in read-only allowlist")
                    continue
            permitted.append(tool)
        return permitted

    def validate_tool_call(self, tool_call: ToolCall) -> tuple[bool, Optional[str]]:
        """
        Validate an incoming tool call requested by the model before execution.
        Returns (is_valid: bool, error_message: Optional[str]).
        """
        fn_name = tool_call.function_name or ""
        if "<|" in fn_name:
            fn_name = re.sub(r"<\|.*?\|>.*", "", fn_name).strip()
            tool_call.function_name = fn_name
        args = tool_call.arguments or {}

        if self.read_only:
            if fn_name in MUTATING_TOOLS_BLOCKLIST:
                msg = (
                    f"PERMISSION DENIED: Tool '{fn_name}' modifies graph state or proposes actions. "
                    f"The GraphOS Investigator operates strictly in READ-ONLY mode."
                )
                logger.warning(f"Guardrail blocked call to {fn_name}: {msg}")
                return False, msg

            if fn_name not in READ_ONLY_ALLOWED_TOOLS:
                msg = (
                    f"PERMISSION DENIED: Tool '{fn_name}' is not in the approved read-only investigation catalog."
                )
                logger.warning(f"Guardrail blocked call to {fn_name}: {msg}")
                return False, msg

        if "depth" in args:
            try:
                depth_val = int(args["depth"])
                if depth_val > 6 or depth_val < 1:
                    return False, f"VALIDATION ERROR: Parameter 'depth' ({depth_val}) must be between 1 and 6."
            except (ValueError, TypeError):
                return False, "VALIDATION ERROR: Parameter 'depth' must be an integer."

        if "max_depth" in args:
            try:
                max_depth_val = int(args["max_depth"])
                if max_depth_val > 8 or max_depth_val < 1:
                    return False, f"VALIDATION ERROR: Parameter 'max_depth' ({max_depth_val}) must be between 1 and 8."
            except (ValueError, TypeError):
                return False, "VALIDATION ERROR: Parameter 'max_depth' must be an integer."

        if "limit" in args:
            try:
                limit_val = int(args["limit"])
                if limit_val > 50 or limit_val < 1:
                    return False, f"VALIDATION ERROR: Parameter 'limit' ({limit_val}) must be between 1 and 50."
            except (ValueError, TypeError):
                return False, "VALIDATION ERROR: Parameter 'limit' must be an integer."

        if "direction" in args:
            dir_val = str(args["direction"]).strip().lower()
            if dir_val not in ("both", "outgoing", "incoming"):
                return False, f"VALIDATION ERROR: Parameter 'direction' ('{dir_val}') must be 'both', 'outgoing', or 'incoming'."

        if fn_name == "run_read_only_cypher_query":
            raw_q = str(args.get("query", ""))
            if not raw_q.strip():
                return False, "VALIDATION ERROR: Parameter 'query' must not be empty."
            if re.search(r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DROP|ALTER|CALL\s+dbms)\b", raw_q, re.IGNORECASE):
                return False, "PERMISSION DENIED: Cypher query contains mutation or administrative operations."
            if len(raw_q) > 1000:
                return False, "VALIDATION ERROR: Cypher query exceeds maximum length of 1000 characters."

        for k, v in args.items():
            if fn_name == "run_read_only_cypher_query" and k == "query":
                continue
            if isinstance(v, str) and len(v) > 500:
                return False, f"VALIDATION ERROR: Parameter '{k}' exceeds maximum length of 500 characters."

        import json
        call_sig = (fn_name, json.dumps(args, sort_keys=True))
        if len(self.recent_tool_calls) >= 2:
            if self.recent_tool_calls[-1] == call_sig and self.recent_tool_calls[-2] == call_sig:
                msg = (
                    f"REPETITION LOOP DETECTED: Tool '{fn_name}' with identical arguments was called multiple times. "
                    "Analyze existing evidence or try a different investigation tool."
                )
                logger.warning(msg)
                return False, msg

        self.recent_tool_calls.append(call_sig)
        return True, None

    def wrap_untrusted_content(self, content: str) -> str:
        """
        Enclose retrieved graph data, documents, and tool responses within untrusted data boundaries
        to prevent prompt injection instructions from overriding application security controls.
        """
        if not content:
            return ""

        max_chars = self.settings.max_result_chars
        truncated = False
        if len(content) > max_chars:
            content = content[:max_chars]
            truncated = True

        wrapped = (
            "<untrusted_graph_data source='falkordb_mcp'>\n"
            f"{content}\n"
            "</untrusted_graph_data>"
        )
        if truncated:
            wrapped += f"\n[Note: Output was truncated to {max_chars} characters by GraphOS guardrail]"
        return wrapped
