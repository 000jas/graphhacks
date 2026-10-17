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

INVESTIGATOR_SYSTEM_PROMPT = """You are GraphOS, a domain-independent, evidence-bound knowledge graph intelligence assistant.
You explore connected data in FalkorDB through read-only MCP tools to answer questions, analyze dependencies, evaluate impact, and verify facts.

### Core Operating Principles:
1. Grounding & Strict Evidence:
   - Every claim, entity, relationship, and metric in your response must be derived directly from actual tool responses.
   - Never assume, invent, or extrapolate entities, relationships, or labels.
   - If a requested entity does not exist or has no connections in the graph, state that fact clearly and objectively.

2. Schema-Driven Exploration:
   - Use the runtime graph schema provided in the context to guide your tool selection and queries.
   - Do not assume specific labels (e.g. Release, Task, Account, Component) or properties (e.g. name, id) unless they exist in the discovered schema.
   - Always respect the specific scope of the user's objective. Do not drift into unrelated entities or default to software release / root cause narratives unless the objective asks for that.

3. Investigation Strategy:
   - Identify focal entities using `search_connected_entities`, `search_entities_advanced`, or `get_entity_profile`.
   - Inspect local connectivity and relationship types using `inspect_entity_neighbors` or `get_entity_profile`.
   - Trace multi-hop connections with `traverse_relationships` or `find_shortest_evidence_path` when path evidence is needed.
   - Use specialized graph algorithms (e.g. impact analysis, community detection, PageRank) only when the objective calls for topological or structural analysis.
   - Stop as soon as the user's question is answered or a genuine graph limitation is reached.

4. Output Delivery:
   - Deliver clear, direct answers tailored to the objective.
   - Summarize the verified facts and evidence retrieved.
   - Highlight any genuine data gaps, limitations, or unverified claims.
   - When appropriate, suggest relevant, concrete next investigative steps based on discovered graph concepts.
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
                messages.append(
                    ChatMessage(
                        role="system",
                        content=(
                            "--- PRIOR CONVERSATION HISTORY (Context Only) ---\n"
                            "Use this history only to resolve referential context or direct follow-up questions. "
                            "Do NOT allow previous investigation topics, entities, hypotheses, or domains to contaminate "
                            "or override the current objective below."
                        ),
                    )
                )
                for ctx_msg in conversation_context:
                    messages.append(ctx_msg)
                messages.append(
                    ChatMessage(
                        role="system",
                        content="--- END OF PRIOR CONVERSATION HISTORY ---",
                    )
                )

            messages.append(
                ChatMessage(
                    role="user",
                    content=(
                        f"CURRENT USER OBJECTIVE:\n{objective}\n\n"
                        "Instructions:\n"
                        "1. Stay strictly within the scope requested by the user. Do not expand into unrelated domains or labels.\n"
                        "2. Formulate a targeted plan: query relevant entities, inspect relationships or neighbors only when necessary for this task.\n"
                        "3. Base your final conclusions strictly on verified data retrieved from the tools. If a record has no relationships, report it as isolated.\n"
                        "4. When the information needed to answer the objective has been gathered, conclude with a clear, factual answer."
                    ),
                )
            )

            steps: list[AgentStep] = []
            total_tool_calls_executed = 0
            final_answer = ""
            unresolved_questions: list[str] = []
            deadline = start_time + (getattr(self.settings, "request_timeout_seconds", 120.0) or 120.0)
            last_call_signature: Optional[str] = None
            consecutive_duplicate_count = 0

            for iteration in range(1, self.settings.max_iterations + 1):
                step_start = time.time()
                logger.debug(f"Investigation Iteration {iteration}/{self.settings.max_iterations}")

                if time.time() >= deadline:
                    timeout_msg = f"Investigation exceeded configured deadline ({self.settings.request_timeout_seconds}s). Concluding with partial results."
                    logger.warning(timeout_msg)
                    _emit("limit_reached", iteration, timeout_msg)
                    unresolved_questions.append(timeout_msg)
                    break

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
                    if time.time() >= deadline:
                        timeout_msg = f"Investigation exceeded deadline ({self.settings.request_timeout_seconds}s) during tool execution."
                        _emit("limit_reached", iteration, timeout_msg)
                        unresolved_questions.append(timeout_msg)
                        break

                    total_tool_calls_executed += 1
                    fn_name = tc.function_name or ""
                    if "<|" in fn_name:
                        import re
                        fn_name = re.sub(r"<\|.*?\|>.*", "", fn_name).strip()
                        tc.function_name = fn_name
                    args = tc.arguments or {}

                    call_sig = f"{fn_name}:{json.dumps(args, sort_keys=True)}"
                    if call_sig == last_call_signature:
                        consecutive_duplicate_count += 1
                    else:
                        consecutive_duplicate_count = 0
                    last_call_signature = call_sig

                    logger.info(f"Tool call #{total_tool_calls_executed}: {fn_name}({args})")
                    _emit("tool_call", iteration, f"Calling tool '{fn_name}'", {"tool": fn_name, "arguments": args})

                    # Suppress redundant schema discovery if graph profile is already cached and valid
                    if fn_name == "discover_graph_schema" and graph_profile.discovery_status == "success" and not args.get("force_refresh"):
                        tool_output = json.dumps({
                            "status": "cached",
                            "message": "Graph schema already discovered and present in your active system context. Please query specific entities or relationships.",
                            "summary": graph_profile.to_summary_dict(),
                        })
                    elif consecutive_duplicate_count >= 2:
                        tool_output = json.dumps({
                            "status": "duplicate_call_warning",
                            "message": f"Tool '{fn_name}' called with identical arguments {consecutive_duplicate_count + 1} times consecutively. Synthesize gathered evidence or select a different entity/tool.",
                        })
                    else:
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

                if time.time() >= deadline or total_tool_calls_executed >= self.settings.max_tool_calls:
                    break

            if not final_answer:
                logger.info("Synthesizing final answer from gathered evidence.")
                _emit("plan", len(steps), "Synthesizing final evidence summary...")
                messages.append(
                    ChatMessage(
                        role="user",
                        content=(
                            f"Please provide your final answer now for the objective: '{objective}'.\n"
                            "Synthesize the verified evidence gathered from the graph tools. "
                            "State the direct answer to the user's question, cite the specific entities and properties retrieved, "
                            "and explicitly note any isolated entities or limitations encountered. Do not speculate beyond verified evidence."
                        ),
                    )
                )
                final_resp = await self.provider.generate_response(messages=messages, tools=[])
                final_answer = final_resp.content or "Investigation concluded."
                if not any("limit" in q.lower() or "timeout" in q.lower() or "budget" in q.lower() or "deadline" in q.lower() for q in unresolved_questions):
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
