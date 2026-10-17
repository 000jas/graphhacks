import asyncio
import pytest

from agent.config import AgentSettings
from agent.models import ChatMessage, ProviderResponse, ToolCall, ToolDefinition
from agent.providers.factory import get_provider
from agent.providers.mock_provider import MockProvider
from agent.providers.nvidia import NvidiaProvider
from agent.providers.openai_provider import OpenAIProvider


def test_mock_provider_tool_generation() -> None:
    async def _run() -> None:
        provider = MockProvider()
        resp = await provider.generate_response(
            messages=[ChatMessage(role="user", content="Why is payments release delayed?")],
            tools=[],
        )
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].function_name == "search_connected_entities"
        assert resp.tool_calls[0].arguments["query"] == "payments"

    asyncio.run(_run())


def test_mock_provider_canned_queue() -> None:
    async def _run() -> None:
        canned = [
            ProviderResponse(content="Step 1 thought", tool_calls=[ToolCall("1", "test_fn", {})]),
            ProviderResponse(content="Final step answer", tool_calls=[]),
        ]
        provider = MockProvider(canned_responses=canned)

        r1 = await provider.generate_response([], [])
        assert r1.content == "Step 1 thought"
        assert len(r1.tool_calls) == 1

        r2 = await provider.generate_response([], [])
        assert r2.content == "Final step answer"
        assert len(r2.tool_calls) == 0

    asyncio.run(_run())


def test_tool_definition_schemas() -> None:
    tool = ToolDefinition(
        name="test_tool",
        description="A test tool",
        parameters={
            "type": "object",
            "properties": {"arg1": {"type": "string"}},
            "required": ["arg1"],
        },
    )

    openai_schema = tool.to_openai_schema()
    assert openai_schema["type"] == "function"
    assert openai_schema["function"]["name"] == "test_tool"
    assert "arg1" in openai_schema["function"]["parameters"]["properties"]

    anthropic_schema = tool.to_anthropic_schema()
    assert anthropic_schema["name"] == "test_tool"
    assert "input_schema" in anthropic_schema


def test_provider_factory_switching() -> None:
    s_mock = AgentSettings(llm_provider="mock", llm_model="mock-v1")
    p_mock = get_provider(s_mock)
    assert isinstance(p_mock, MockProvider)
    assert p_mock.get_model_info()["provider"] == "mock"

    s_nvidia = AgentSettings(
        llm_provider="nvidia",
        nvidia_api_key="nvapi-test123456",
        llm_model="openai/gpt-oss-20b",
    )
    p_nvidia = get_provider(s_nvidia)
    assert isinstance(p_nvidia, NvidiaProvider)
    assert p_nvidia.get_model_info()["provider"] == "nvidia"

    s_openai = AgentSettings(
        llm_provider="openai",
        openai_api_key="sk-test123456",
        llm_model="gpt-4o",
    )
    p_openai = get_provider(s_openai)
    assert isinstance(p_openai, OpenAIProvider)
    assert p_openai.get_model_info()["provider"] == "openai"
