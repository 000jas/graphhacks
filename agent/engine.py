from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Optional

from agent.config import AgentSettings, settings as default_settings
from agent.evidence import EvidenceCollector
from agent.guardrails import GuardrailManager
from agent.mcp_client import MCPClientManager
from agent.models import (
    AgentResult,
    AgentStep,
    ChatMessage,
    InvestigationEvent,
    ProviderResponse,
    ToolCall,
    ToolDefinition,
)
from agent.providers.base import BaseLLMProvider
from agent.providers.factory import get_provider
from agent.schema_context import GraphProfile, SchemaContextManager

logger = logging.getLogger("graphos.agent.engine")

INVESTIGATOR_SYSTEM_PROMPT = """You are the GraphOS Investigator, a direct, evidence-bound knowledge graph intelligence assistant.
Your goal is to inspect connected data in FalkorDB via MCP tools, uncover the root cause, and present a clean, concise, human-friendly explanation with interactive next options.

### Operational Guidelines:
1. Grounding: Every finding must be based on actual graph data retrieved via tools. Do not invent or assume entities or relationships.
2. Direct Investigation Strategy:
   - Find focal entities using `search_connected_entities` or `search_entities_advanced`.
   - Inspect connections using `traverse_relationships` (following relationship types like BLOCKED_BY, REQUIRES, ASSIGNED_TO, DEPLOYS, HAS_RELEASE) or `get_entity_profile`.
   - Continue traversing along the dependency chain until you uncover the blocker, bottleneck, or root cause.
3. Keep Output Clean, Direct, and Simple:
   - Avoid generic boilerplate, academic intros, or giant multi-column tables.
   - Deliver clear, actionable reasoning in plain English that anyone can read in 15 seconds.

### Output Structure:
When your investigation is complete, present your findings using this clean structure:

### 🎯 Root Cause Summary
(1-2 clear sentences directly answering why the issue occurred, naming the specific blocker or reason.)

### 🔗 Chain of Evidence
(A clear, visual step-by-step trace showing how entities connect from the problem to the root cause, using arrows):
`[Focal Entity]` ➔ `[Relationship]` ➔ `[Intermediate Node / Blocker]` ➔ `[Root Issue / Assigned Owner]`

### 💡 Key Contributing Facts
- 2-3 short bullet points highlighting the specific facts (e.g. status, assigned owner, availability, leave/incident event).

### ⚡ Suggested Next Actions
Present 2-3 clear, concrete next options the user can take:
[1] <Concrete action 1, e.g. reassign task or check alternative reviewer>
[2] <Concrete action 2, e.g. simulate bypass or assess downstream impact>
[3] <Concrete action 3, e.g. query decision memory or audit logs>
"""


class GraphOSInvestigator:
    """
    Main Agent Engine managing the provider-agnostic, evidence-bound investigation loop
    connected to FalkorDB via MCP.
    """

    def __init__(
        self,
        settings: Optional[AgentSettings] = None,
        provider: Optional[BaseLLMProvider] = None,
        mcp_client: Optional[MCPClientManager] = None,
    ) -> None:
        self.settings = settings or default_settings
        self.provider = provider or get_provider(self.settings)
        self.mcp_client = mcp_client or MCPClientManager(self.settings)
        self.guardrails = GuardrailManager(self.settings)
        self.schema_manager = SchemaContextManager(ttl_seconds=300.0)

    async def get_runtime_schema(self, force_refresh: bool = False) -> GraphProfile:
        """Retrieve or refresh the runtime graph schema profile."""
        if not self.mcp_client.session:
            await self.mcp_client.connect()
        return await self.schema_manager.get_or_discover_profile(
            self.mcp_client,
            tenant_graph=self.settings.graph_name,
            force_refresh=force_refresh,
        )

    async def investigate(
        self,
        objective: str,
        on_step_callback: Optional[Callable[[AgentStep], None]] = None,
        on_event_callback: Optional[Callable[[InvestigationEvent], None]] = None,
        conversation_context: Optional[list[ChatMessage]] = None,
    ) -> AgentResult:
        """
        Execute an end-to-end investigation against the knowledge graph for a user objective.
        Supports streaming event updates and multi-turn conversational context.
        """
        start_time = time.time()
        objective = objective.strip()
        if not objective:
            raise ValueError("Investigation objective must not be empty")

        def _emit(event_type: str, iteration: int, message: str, metadata: Optional[dict[str, Any]] = None) -> None:
            if on_event_callback:
                on_event_callback(
                    InvestigationEvent(
                        event_type=event_type,
                        iteration=iteration,
                        message=message,
                        metadata=metadata or {},
                    )
                )

        logger.info(f"Starting GraphOS investigation: '{objective}'")
        _emit("plan", 0, f"Investigating objective: {objective}", {"objective": objective})
        evidence = EvidenceCollector()

        should_disconnect = False
        if not self.mcp_client.session:
            _emit("info", 0, f"Connecting to MCP server via {self.settings.mcp_transport}...")
            await self.mcp_client.connect()
            should_disconnect = True

        try:
            raw_tools = await self.mcp_client.discover_tools()
            permitted_tools = self.guardrails.filter_available_tools(raw_tools)
            logger.info(
                f"Discovered {len(raw_tools)} tools from MCP server. "
                f"Exposing {len(permitted_tools)} read-only tools to provider."
            )
            _emit(
                "info",
                0,
                f"Discovered {len(raw_tools)} MCP tools. Guardrails approved {len(permitted_tools)} read-only tools.",
                {"raw_tool_count": len(raw_tools), "permitted_count": len(permitted_tools)},
            )

            graph_profile = await self.schema_manager.get_or_discover_profile(
                self.mcp_client,
                tenant_graph=self.settings.graph_name,
            )
            _emit(
                "schema_discovered",
                0,
                f"Active Graph: '{graph_profile.graph_identity}' | Domain: {graph_profile.inferred_domain} "
                f"({graph_profile.total_nodes} nodes, {graph_profile.total_edges} edges, {len(graph_profile.node_kinds)} kinds)",
                graph_profile.to_summary_dict(),
            )

            messages: list[ChatMessage] = [
                ChatMessage(role="system", content=INVESTIGATOR_SYSTEM_PROMPT),
                ChatMessage(role="system", content=graph_profile.to_prompt_context()),
            ]

            if conversation_context:
                for ctx_msg in conversation_context:
                    messages.append(ctx_msg)

            messages.append(
                ChatMessage(
                    role="user",
                    content=(
                        f"INVESTIGATION OBJECTIVE:\n{objective}\n\n"
                        "Please inspect the connected knowledge graph using your available tools. "
                        "Discover the relevant entities, trace their dependencies, and explain the root cause with verified evidence."
                    ),
                )
            )

            steps: list[AgentStep] = []
            total_tool_calls_executed = 0
            final_answer = ""
            unresolved_questions: list[str] = []

            for iteration in range(1, self.settings.max_iterations + 1):
                step_start = time.time()
                logger.debug(f"Investigation Iteration {iteration}/{self.settings.max_iterations}")

                if total_tool_calls_executed >= self.settings.max_tool_calls:
                    limit_msg = f"Reached maximum tool call budget ({self.settings.max_tool_calls}). Concluding investigation."
                    logger.warning(limit_msg)
                    _emit("limit_reached", iteration, limit_msg)
                    unresolved_questions.append("Investigation reached maximum tool call budget before exhaustive exploration.")
                    break

                _emit("plan", iteration, f"Reasoning over evidence graph (step {iteration}/{self.settings.max_iterations})...")
                provider_response = await self.provider.generate_response(
                    messages=messages,
                    tools=permitted_tools,
                )

                thought = provider_response.content
                requested_tool_calls = provider_response.tool_calls

                if thought:
                    _emit("thought", iteration, thought.strip().split("\n")[0][:120], {"full_thought": thought})

                if not requested_tool_calls:
                    final_answer = thought or "Investigation completed with no further tool calls."
                    step = AgentStep(
                        iteration=iteration,
                        thought=thought,
                        tool_calls=[],
                        tool_results=[],
                        duration_seconds=time.time() - step_start,
                    )
                    steps.append(step)
                    if on_step_callback:
                        on_step_callback(step)
                    break

                tool_results_for_step: list[dict[str, Any]] = []

                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=thought,
                        tool_calls=requested_tool_calls,
                    )
                )

                for tc in requested_tool_calls:
                    total_tool_calls_executed += 1
                    fn_name = tc.function_name or ""
                    if "<|" in fn_name:
                        import re
                        fn_name = re.sub(r"<\|.*?\|>.*", "", fn_name).strip()
                        tc.function_name = fn_name
                    args = tc.arguments or {}

                    logger.info(f"Tool call #{total_tool_calls_executed}: {fn_name}({args})")
                    _emit("tool_call", iteration, f"Calling tool '{fn_name}'", {"tool": fn_name, "arguments": args})

                    is_valid, validation_error = self.guardrails.validate_tool_call(tc)
                    if not is_valid:
                        tool_output = json.dumps({"guardrail_rejection": validation_error})
                        _emit("guardrail_blocked", iteration, f"Guardrail blocked '{fn_name}': {validation_error}", {"tool": fn_name, "reason": validation_error})
                    else:
                        tool_output = await self.mcp_client.call_tool(fn_name, args)

                        evidence.ingest_tool_output(fn_name, args, tool_output)
                        _emit("tool_result", iteration, f"Retrieved data from '{fn_name}' ({len(tool_output)} bytes)", {"tool": fn_name, "output_length": len(tool_output)})

                    safe_output = self.guardrails.wrap_untrusted_content(tool_output)

                    tool_results_for_step.append({
                        "call_id": tc.id,
                        "tool": fn_name,
                        "arguments": args,
                        "result_length": len(tool_output),
                    })

                    messages.append(
                        ChatMessage(
                            role="tool",
                            name=fn_name,
                            tool_call_id=tc.id,
                            content=safe_output,
                        )
                    )

                step = AgentStep(
                    iteration=iteration,
                    thought=thought,
                    tool_calls=requested_tool_calls,
                    tool_results=tool_results_for_step,
                    duration_seconds=time.time() - step_start,
                )
                steps.append(step)
                if on_step_callback:
                    on_step_callback(step)

            if not final_answer:
                logger.info("Synthesizing final answer from gathered evidence following iteration limit.")
                _emit("plan", len(steps), "Synthesizing final evidence summary following iteration limit...")
                messages.append(
                    ChatMessage(
                        role="user",
                        content=(
                            "Please provide your final answer now based on the evidence gathered so far. "
                            "State the root cause clearly, explain the chain of evidence connecting the problem to the cause, "
                            "and provide 2-3 suggested next actions."
                        ),
                    )
                )
                final_resp = await self.provider.generate_response(messages=messages, tools=[])
                final_answer = final_resp.content or "Investigation concluded."
                if "iteration limit" not in " ".join(unresolved_questions):
                    unresolved_questions.append("Exhausted configured iteration budget before completing all paths.")

            duration = round(time.time() - start_time, 2)
            evidence_summary = evidence.generate_summary()
            unresolved_questions.extend(evidence_summary.get("unresolved_gaps", []))

            result = AgentResult(
                objective=objective,
                success=True,
                final_answer=final_answer,
                evidence_summary=evidence_summary,
                steps=steps,
                total_iterations=len(steps),
                total_tool_calls=total_tool_calls_executed,
                duration_seconds=duration,
                provider_info=self.provider.get_model_info(),
                unresolved_questions=list(set(unresolved_questions)),
            )
            _emit("complete", len(steps), f"Investigation completed ({duration}s, {total_tool_calls_executed} tool calls)", {"duration": duration, "tool_calls": total_tool_calls_executed, "iterations": len(steps)})
            logger.info(
                f"Investigation complete in {duration}s ({len(steps)} iterations, {total_tool_calls_executed} tool calls)"
            )
            return result


        finally:
            if should_disconnect:
                await self.mcp_client.disconnect()
