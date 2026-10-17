from __future__ import annotations

import logging
from typing import Optional

from agent.config import AgentSettings
from agent.providers.anthropic_provider import AnthropicProvider
from agent.providers.base import BaseLLMProvider
from agent.providers.mock_provider import MockProvider
from agent.providers.nvidia import NvidiaProvider
from agent.providers.ollama_provider import OllamaProvider
from agent.providers.openai_provider import OpenAIProvider

logger = logging.getLogger("graphos.agent.provider.factory")


def get_provider(settings: AgentSettings) -> BaseLLMProvider:
    """
    Construct and return the configured BaseLLMProvider adapter based on settings.
    Validates required credentials only for the selected provider.
    """
    settings.validate_provider_configuration()
    provider_name = settings.llm_provider.strip().lower()

    if provider_name == "nvidia":
        logger.info(f"Initializing NvidiaProvider (model: {settings.llm_model}, endpoint: {settings.llm_api_base})")
        return NvidiaProvider(
            api_key=settings.nvidia_api_key or "",
            model=settings.llm_model,
            api_base=settings.llm_api_base,
            timeout_seconds=settings.request_timeout_seconds,
        )

    elif provider_name == "openai":
        logger.info(f"Initializing OpenAIProvider (model: {settings.llm_model})")
        return OpenAIProvider(
            api_key=settings.openai_api_key or "",
            model=settings.llm_model,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.request_timeout_seconds,
        )

    elif provider_name == "anthropic":
        logger.info(f"Initializing AnthropicProvider (model: {settings.llm_model})")
        return AnthropicProvider(
            api_key=settings.anthropic_api_key or "",
            model=settings.llm_model,
            base_url=settings.anthropic_base_url,
            timeout_seconds=settings.request_timeout_seconds,
        )

    elif provider_name == "ollama":
        logger.info(f"Initializing OllamaProvider (endpoint: {settings.ollama_base_url}, model: {settings.ollama_model})")
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout_seconds=settings.request_timeout_seconds,
        )

    elif provider_name == "mock":
        logger.info("Initializing MockProvider in-memory")
        return MockProvider(model_name=settings.llm_model)

    else:
        raise ValueError(f"Unsupported LLM provider: '{provider_name}'")
