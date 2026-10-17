import asyncio
import json
import pytest

from agent.config import AgentSettings
from agent.mcp_client import MCPClientManager


def test_mcp_client_dynamic_discovery() -> None:
    async def _run() -> None:
        settings = AgentSettings(mcp_transport="stdio")
        async with MCPClientManager(settings) as client:
            tools = await client.discover_tools()
            assert len(tools) >= 12
            tool_names = [t.name for t in tools]
            assert "search_connected_entities" in tool_names
            assert "get_entity_profile" in tool_names
            assert "traverse_relationships" in tool_names
            assert "find_shortest_evidence_path" in tool_names

    asyncio.run(_run())


def test_mcp_client_tool_execution() -> None:
    async def _run() -> None:
        settings = AgentSettings(mcp_transport="stdio")
        async with MCPClientManager(settings) as client:
            raw_output = await client.call_tool(
                "search_connected_entities",
                {"query": "payments", "limit": 2},
            )
            assert raw_output
            data = json.loads(raw_output)
            assert "entities" in data
            assert len(data["entities"]) > 0

    asyncio.run(_run())


def test_mcp_client_invalid_tool_handling() -> None:
    async def _run() -> None:
        settings = AgentSettings(mcp_transport="stdio")
        async with MCPClientManager(settings) as client:
            res = await client.call_tool("nonexistent_tool_xyz", {})
            assert "unknown" in res.lower() or "failed" in res.lower() or "error" in res.lower()

    asyncio.run(_run())
