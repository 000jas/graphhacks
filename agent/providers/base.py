from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from agent.models import ChatMessage, ProviderResponse, ToolDefinition


class ProviderError(Exception):
    """Base exception for LLM provider communication and inference errors."""


class ProviderAuthenticationError(ProviderError):
    """Raised when provider credentials, permissions, or API keys are rejected."""


class ProviderTimeoutError(ProviderError):
    """Raised when an inference call times out."""


class BaseLLMProvider(ABC):
    """Abstract provider interface encapsulating LLM vendor differences."""

    @abstractmethod
    async def generate_response(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
    ) -> ProviderResponse:
        """
        Execute an inference request with conversational history and available tools,
        returning a normalized ProviderResponse.
        """
        pass

    @abstractmethod
    def get_model_info(self) -> dict[str, Any]:
        """Return non-sensitive metadata regarding the active provider and model."""
        pass

    @abstractmethod
    async def validate_connection(self) -> tuple[bool, str]:
        """
        Test reachability and authentication with the provider.
        Returns (success: bool, diagnostic_message: str).
        """
        pass
