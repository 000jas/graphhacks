import asyncio
import pytest

from agent.config import AgentSettings
from agent.engine import GraphOSInvestigator
from agent.mcp_client import MCPClientManager
from agent.providers.mock_provider import MockProvider


def test_investigation_payments_release_delayed() -> None:
    """
    Primary end-to-end investigation:
    'Why is the payments release delayed? Investigate the connected data and explain the root cause with supporting evidence.'
    Tests live MCP server over stdio connected to cloud FalkorDB.
    """
    async def _run() -> None:
        settings = AgentSettings(
            llm_provider="mock",
            mcp_transport="stdio",
            max_iterations=6,
            max_tool_calls=10,
        )

        async with MCPClientManager(settings) as client:
            investigator = GraphOSInvestigator(
                settings=settings,
                provider=MockProvider(),
                mcp_client=client,
            )

            result = await investigator.investigate(
                "Why is the payments release delayed? Investigate the connected data and explain the root cause with supporting evidence."
            )

            assert result.success is True
            assert result.total_iterations >= 2
            assert result.total_tool_calls >= 2
            assert "payments" in result.final_answer.lower()
            assert "security" in result.final_answer.lower() or "review" in result.final_answer.lower()
            entities = result.evidence_summary.get("entities", [])
            assert len(entities) > 0

    asyncio.run(_run())


def test_investigation_unknown_entity_gap_handling() -> None:
    """
    Secondary end-to-end investigation with unknown/disconnected entity:
    Confirms agent reports insufficient evidence rather than hallucinating.
    """
    async def _run() -> None:
        settings = AgentSettings(
            llm_provider="mock",
            mcp_transport="stdio",
            max_iterations=4,
            max_tool_calls=6,
        )

        async with MCPClientManager(settings) as client:
            investigator = GraphOSInvestigator(
                settings=settings,
                provider=MockProvider(),
                mcp_client=client,
            )

            result = await investigator.investigate(
                "Investigate the status of QuantumTeleportationService and explain why its release is blocked."
            )

            assert result.success is True
            assert "no connected entities found" in result.final_answer.lower() or "insufficient" in result.final_answer.lower() or "unresolved" in result.final_answer.lower()

    asyncio.run(_run())
