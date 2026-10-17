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

logger = logging.getLogger("graphos.agent.provider.openai")


class OpenAIProvider(BaseLLMProvider):
    """Provider adapter for OpenAI models (e.g. gpt-4o, gpt-4-turbo)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: int = 120,
    ) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required to initialize OpenAIProvider")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get_model_info(self) -> dict[str, Any]:
        return {
            "provider": "openai",
            "model": self.model,
            "base_url": self.base_url,
            "api_key_configured": bool(self.api_key),
            "api_key_masked": mask_secret(self.api_key),
        }

    async def validate_connection(self) -> tuple[bool, str]:
        url = f"{self.base_url}/models"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    return True, f"OpenAI endpoint reachable. Model: {self.model}"
                elif resp.status_code in (401, 403):
                    return False, f"OpenAI authentication failed (HTTP {resp.status_code}): {resp.text}"
                else:
                    return False, f"OpenAI endpoint error (HTTP {resp.status_code}): {resp.text}"
        except Exception as exc:
            return False, f"OpenAI connection error: {type(exc).__name__}: {exc}"

    async def generate_response(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
    ) -> ProviderResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [msg.to_dict() for msg in messages],
            "temperature": 0.1,
        }
        if tools:
            payload["tools"] = [t.to_openai_schema() for t in tools]
            payload["tool_choice"] = "auto"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)

            if resp.status_code == 200:
                body = resp.json()
                choice = body["choices"][0]
                message_data = choice["message"]
                content = message_data.get("content")

                tool_calls: list[ToolCall] = []
                for idx, rtc in enumerate(message_data.get("tool_calls") or []):
                    fn = rtc["function"]
                    raw_args = fn.get("arguments", "{}")
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except Exception:
                        args = {"raw": raw_args}

                    tool_calls.append(
                        ToolCall(
                            id=rtc.get("id") or f"call_openai_{idx}",
                            function_name=fn["name"],
                            arguments=args,
                        )
                    )

                return ProviderResponse(
                    content=content,
                    tool_calls=tool_calls,
                    finish_reason="tool_calls" if tool_calls else choice.get("finish_reason", "stop"),
                    usage=body.get("usage", {}),
                    raw_response=body,
                )

            elif resp.status_code in (401, 403):
                raise ProviderAuthenticationError(f"OpenAI authentication failed: {resp.text}")
            else:
                raise ProviderError(f"OpenAI error (HTTP {resp.status_code}): {resp.text}")

        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"OpenAI request timed out after {self.timeout_seconds}s") from exc
        except (ProviderError, ProviderAuthenticationError, ProviderTimeoutError):
            raise
        except Exception as exc:
            raise ProviderError(f"OpenAI call failed: {exc}") from exc
