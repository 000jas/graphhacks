from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from agent.models import ChatMessage, ProviderResponse, ToolCall, ToolDefinition
from agent.providers.base import (
    BaseLLMProvider,
    ProviderError,
    ProviderTimeoutError,
)

logger = logging.getLogger("graphos.agent.provider.ollama")


class OllamaProvider(BaseLLMProvider):
    """Provider adapter for local Ollama instances (e.g. qwen2.5:7b, llama3.1:8b)."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b",
        timeout_seconds: int = 120,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def get_model_info(self) -> dict[str, Any]:
        return {
            "provider": "ollama",
            "model": self.model,
            "base_url": self.base_url,
            "api_key_configured": False,
        }

    async def validate_connection(self) -> tuple[bool, str]:
        url = f"{self.base_url}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    has_model = any(self.model in m for m in models)
                    if has_model:
                        return True, f"Ollama reachable. Model '{self.model}' is locally available."
                    return True, f"Ollama reachable, but '{self.model}' was not found in: {models}"
                return False, f"Ollama returned HTTP {resp.status_code}: {resp.text}"
        except Exception as exc:
            return False, f"Ollama connection failed at '{self.base_url}': {type(exc).__name__}: {exc}"

    async def generate_response(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
    ) -> ProviderResponse:
        url = f"{self.base_url}/api/chat"

        ollama_messages = []
        for msg in messages:
            m = {"role": msg.role, "content": msg.content or ""}
            if msg.tool_calls:
                m["tool_calls"] = [
                    {"function": {"name": tc.function_name, "arguments": tc.arguments}}
                    for tc in msg.tool_calls
                ]
            ollama_messages.append(m)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {"temperature": 0.1},
        }
        if tools:
            payload["tools"] = [t.to_openai_schema() for t in tools]

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(url, json=payload)

            if resp.status_code == 200:
                body = resp.json()
                msg_data = body.get("message", {})
                content = msg_data.get("content")

                tool_calls: list[ToolCall] = []
                for idx, rtc in enumerate(msg_data.get("tool_calls", [])):
                    fn = rtc.get("function", {})
                    fn_name = fn.get("name", "")
                    fn_args = fn.get("arguments", {})
                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except Exception:
                            fn_args = {"raw": fn_args}

                    tool_calls.append(
                        ToolCall(
                            id=f"call_ollama_{idx}",
                            function_name=fn_name,
                            arguments=fn_args,
                        )
                    )

                return ProviderResponse(
                    content=content,
                    tool_calls=tool_calls,
                    finish_reason="tool_calls" if tool_calls else "stop",
                    usage={},
                    raw_response=body,
                )
            else:
                raise ProviderError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")

        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"Ollama timed out after {self.timeout_seconds}s") from exc
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Ollama inference error: {exc}") from exc
