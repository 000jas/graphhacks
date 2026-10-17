from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from agent.config import mask_secret
from agent.models import ChatMessage, ProviderResponse, ToolCall, ToolDefinition
from agent.providers.base import (
    BaseLLMProvider,
    ProviderAuthenticationError,
    ProviderError,
    ProviderTimeoutError,
)

logger = logging.getLogger("graphos.agent.provider.anthropic")


class AnthropicProvider(BaseLLMProvider):
    """Provider adapter for Anthropic Claude models (e.g. claude-3-5-sonnet-20241022)."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        base_url: str = "https://api.anthropic.com",
        timeout_seconds: int = 120,
    ) -> None:
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required to initialize AnthropicProvider")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get_model_info(self) -> dict[str, Any]:
        return {
            "provider": "anthropic",
            "model": self.model,
            "base_url": self.base_url,
            "api_key_configured": bool(self.api_key),
            "api_key_masked": mask_secret(self.api_key),
        }

    async def validate_connection(self) -> tuple[bool, str]:
        """Test authentication with Anthropic."""
        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": 5,
            "messages": [{"role": "user", "content": "ping"}],
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    return True, f"Anthropic endpoint reachable. Model: {self.model}"
                elif resp.status_code in (401, 403):
                    return False, f"Anthropic authentication failed (HTTP {resp.status_code}): {resp.text}"
                else:
                    return False, f"Anthropic endpoint returned HTTP {resp.status_code}: {resp.text}"
        except Exception as exc:
            return False, f"Anthropic connection error: {type(exc).__name__}: {exc}"

    async def generate_response(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
    ) -> ProviderResponse:
        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        system_prompt = ""
        anthropic_messages: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content or ""
            elif msg.role == "user":
                anthropic_messages.append({"role": "user", "content": msg.content or ""})
            elif msg.role == "assistant":
                content_blocks: list[dict[str, Any]] = []
                if msg.content:
                    content_blocks.append({"type": "text", "text": msg.content})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.function_name,
                            "input": tc.arguments,
                        })
                anthropic_messages.append({"role": "assistant", "content": content_blocks or ""})
            elif msg.role == "tool":
                anthropic_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id or "unknown",
                            "content": msg.content or "",
                        }
                    ],
                })

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": 2048,
            "temperature": 0.1,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if tools:
            payload["tools"] = [t.to_anthropic_schema() for t in tools]

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)

            if resp.status_code == 200:
                body = resp.json()
                text_content = ""
                normalized_tool_calls: list[ToolCall] = []

                for block in body.get("content", []):
                    b_type = block.get("type")
                    if b_type == "text":
                        text_content += block.get("text", "")
                    elif b_type == "tool_use":
                        normalized_tool_calls.append(
                            ToolCall(
                                id=block.get("id") or f"call_{len(normalized_tool_calls)}",
                                function_name=block.get("name", ""),
                                arguments=block.get("input", {}),
                            )
                        )

                usage = body.get("usage", {})
                return ProviderResponse(
                    content=text_content or None,
                    tool_calls=normalized_tool_calls,
                    finish_reason="tool_calls" if normalized_tool_calls else body.get("stop_reason", "stop"),
                    usage={
                        "prompt_tokens": usage.get("input_tokens", 0),
                        "completion_tokens": usage.get("output_tokens", 0),
                        "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                    },
                    raw_response=body,
                )

            elif resp.status_code in (401, 403):
                raise ProviderAuthenticationError(f"Anthropic authentication failed: {resp.text}")
            else:
                raise ProviderError(f"Anthropic error (HTTP {resp.status_code}): {resp.text}")

        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"Anthropic request timed out after {self.timeout_seconds}s") from exc
        except (ProviderError, ProviderAuthenticationError, ProviderTimeoutError):
            raise
        except Exception as exc:
            raise ProviderError(f"Anthropic call failed: {exc}") from exc
