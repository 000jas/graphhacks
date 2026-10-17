from __future__ import annotations

import json
import logging
import re
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

logger = logging.getLogger("graphos.agent.provider.nvidia")


class NvidiaProvider(BaseLLMProvider):
    """
    Provider adapter for NVIDIA AI Foundation Models (Default: openai/gpt-oss-20b).
    Communicates with NVIDIA's OpenAI-compatible integrate endpoint.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "openai/gpt-oss-20b",
        api_base: str = "https://integrate.api.nvidia.com/v1",
        timeout_seconds: int = 120,
    ) -> None:
        if not api_key:
            raise ValueError("NVIDIA_API_KEY is required to initialize NvidiaProvider")
        self.api_key = api_key
        self.model = model
        self.api_base = api_base.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get_model_info(self) -> dict[str, Any]:
        return {
            "provider": "nvidia",
            "model": self.model,
            "api_base": self.api_base,
            "api_key_configured": bool(self.api_key),
            "api_key_masked": mask_secret(self.api_key),
        }

    async def validate_connection(self) -> tuple[bool, str]:
        """Verify reachability and authorization of the NVIDIA endpoint."""
        url = f"{self.api_base}/models"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    available_models = [m.get("id") for m in data.get("data", [])]
                    if self.model in available_models:
                        return True, f"NVIDIA endpoint reachable. Model '{self.model}' is available."
                    return True, f"NVIDIA endpoint reachable ({len(available_models)} models discovered). Note: '{self.model}' not in primary catalog."
                elif resp.status_code in (401, 403):
                    return False, f"NVIDIA API authentication failed (HTTP {resp.status_code}): {resp.text}"
                else:
                    return False, f"NVIDIA endpoint error (HTTP {resp.status_code}): {resp.text}"
        except httpx.TimeoutException:
            return False, f"Connection to NVIDIA endpoint '{self.api_base}' timed out."
        except Exception as exc:
            return False, f"Failed to connect to NVIDIA endpoint: {type(exc).__name__}: {exc}"

    async def generate_response(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
    ) -> ProviderResponse:
        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        formatted_messages = [msg.to_dict() for msg in messages]
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": 0.1,
            "max_tokens": 2048,
        }

        if tools:
            payload["tools"] = [t.to_openai_schema() for t in tools]
            payload["tool_choice"] = "auto"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)

            if resp.status_code == 200:
                body = resp.json()
                choices = body.get("choices", [])
                if not choices:
                    raise ProviderError("NVIDIA API returned empty completion choices")

                choice = choices[0]
                message_data = choice.get("message", {})
                content = message_data.get("content")
                finish_reason = choice.get("finish_reason", "stop")

                normalized_tool_calls: list[ToolCall] = []
                raw_tool_calls = message_data.get("tool_calls") or []

                for idx, rtc in enumerate(raw_tool_calls):
                    fn = rtc.get("function", {})
                    fn_name = fn.get("name", "") or ""
                    if "<|" in fn_name:
                        fn_name = re.sub(r"<\|.*?\|>.*", "", fn_name).strip()
                    raw_args = fn.get("arguments", "{}")

                    if isinstance(raw_args, dict):
                        parsed_args = raw_args
                    elif isinstance(raw_args, str):
                        try:
                            parsed_args = json.loads(raw_args) if raw_args.strip() else {}
                        except json.JSONDecodeError:
                            logger.warning(f"Malformed JSON arguments from NVIDIA model: {raw_args}")
                            parsed_args = {"raw_arguments": raw_args}
                    else:
                        parsed_args = {}

                    normalized_tool_calls.append(
                        ToolCall(
                            id=rtc.get("id") or f"call_nvidia_{idx}",
                            function_name=fn_name,
                            arguments=parsed_args,
                        )
                    )

                usage = body.get("usage", {})
                return ProviderResponse(
                    content=content,
                    tool_calls=normalized_tool_calls,
                    finish_reason="tool_calls" if normalized_tool_calls else finish_reason,
                    usage={
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    },
                    raw_response=body,
                )

            elif resp.status_code in (401, 403):
                err_msg = f"NVIDIA authorization failed (HTTP {resp.status_code}): {resp.text}"
                logger.error(err_msg)
                raise ProviderAuthenticationError(err_msg)
            else:
                err_msg = f"NVIDIA API error (HTTP {resp.status_code}): {resp.text}"
                logger.error(err_msg)
                raise ProviderError(err_msg)

        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"NVIDIA request timed out after {self.timeout_seconds}s"
            ) from exc
        except (ProviderError, ProviderAuthenticationError, ProviderTimeoutError):
            raise
        except Exception as exc:
            raise ProviderError(f"NVIDIA request failed: {type(exc).__name__}: {exc}") from exc
