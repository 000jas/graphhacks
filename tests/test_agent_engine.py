import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest

from agent.config import AgentSettings
from agent.engine import GraphOSInvestigator
from agent.models import (
    AgentStep,
    ChatMessage,
    ProviderResponse,
    ToolCall,
    ToolDefinition,
)
from agent.providers.mock_provider import MockProvider


def test_agent_engine_immediate_conclusion() -> None:
    async def _run() -> None:
        settings = AgentSettings(llm_provider="mock", max_iterations=5)
        provider = MockProvider(
            canned_responses=[
                ProviderResponse(content="Final answer immediately with no tool calls.", tool_calls=[])
            ]
        )

        mock_mcp = AsyncMock()
        mock_mcp.session = MagicMock()
        mock_mcp.discover_tools.return_value = [
            ToolDefinition("search_connected_entities", "search", {})
        ]

        agent = GraphOSInvestigator(settings=settings, provider=provider, mcp_client=mock_mcp)

        steps_called = []
        def _on_step(s: AgentStep) -> None:
            steps_called.append(s)

        res = await agent.investigate("Simple test question", on_step_callback=_on_step)

        assert res.success is True
        assert res.total_iterations == 1
        assert res.total_tool_calls == 0
        assert "Final answer immediately" in res.final_answer
        assert len(steps_called) == 1

    asyncio.run(_run())


def test_agent_engine_bounded_iteration_limit() -> None:
    async def _run() -> None:
        settings = AgentSettings(llm_provider="mock", max_iterations=2, max_tool_calls=10)

        responses = [
            ProviderResponse(content="Step 1", tool_calls=[ToolCall("1", "search_connected_entities", {"query": "test1"})]),
            ProviderResponse(content="Step 2", tool_calls=[ToolCall("2", "search_connected_entities", {"query": "test2"})]),
            ProviderResponse(content="Synthesized final answer after limit", tool_calls=[]),
        ]
        provider = MockProvider(canned_responses=responses)

        mock_mcp = AsyncMock()
        mock_mcp.session = MagicMock()
        mock_mcp.discover_tools.return_value = [
            ToolDefinition("search_connected_entities", "search", {"type": "object", "properties": {"query": {"type": "string"}}})
        ]
        mock_mcp.call_tool.return_value = '{"entities": []}'

        agent = GraphOSInvestigator(settings=settings, provider=provider, mcp_client=mock_mcp)
        res = await agent.investigate("Will this loop forever?")

        assert res.success is True
        assert res.total_iterations == 2
        assert res.total_tool_calls == 2
        assert "Synthesized final answer" in res.final_answer
        assert any("iteration" in q.lower() for q in res.unresolved_questions)

    asyncio.run(_run())


def test_agent_engine_tool_budget_limit() -> None:
    async def _run() -> None:
        settings = AgentSettings(llm_provider="mock", max_iterations=10, max_tool_calls=1)

        responses = [
            ProviderResponse(content="Step 1", tool_calls=[ToolCall("1", "search_connected_entities", {"query": "test1"})]),
            ProviderResponse(content="Synthesized final answer after tool budget", tool_calls=[]),
        ]
        provider = MockProvider(canned_responses=responses)

        mock_mcp = AsyncMock()
        mock_mcp.session = MagicMock()
        mock_mcp.discover_tools.return_value = [
            ToolDefinition("search_connected_entities", "search", {})
        ]
        mock_mcp.call_tool.return_value = '{"entities": []}'

        agent = GraphOSInvestigator(settings=settings, provider=provider, mcp_client=mock_mcp)
        res = await agent.investigate("Tool budget test")

        assert res.success is True
        assert res.total_tool_calls == 1
        assert any("budget" in q.lower() for q in res.unresolved_questions)

    asyncio.run(_run())
