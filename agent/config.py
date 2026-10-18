from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from dotenv import find_dotenv, load_dotenv

CURRENT_DIR = Path(__file__).resolve().parent
PARENT_ENV = CURRENT_DIR.parent / ".env"
AGENT_ENV = CURRENT_DIR / ".env"

if PARENT_ENV.exists():
    load_dotenv(dotenv_path=PARENT_ENV)
elif AGENT_ENV.exists():
    load_dotenv(dotenv_path=AGENT_ENV)
else:
    load_dotenv(find_dotenv())


def mask_secret(secret: Optional[str]) -> str:
    """Mask sensitive credentials for safe logging and diagnostics."""
    if not secret:
        return "<not set>"
    s = secret.strip()
    if len(s) <= 8:
        return "****"
    return f"{s[:4]}...{s[-4:]}"


@dataclass
class AgentSettings:
    """Configuration settings for the GraphOS AI Agent and Provider Layer."""

    llm_provider: str = field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "nvidia").strip().lower()
    )

    llm_model: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL", "openai/gpt-oss-20b").strip()
    )

    llm_api_base: str = field(
        default_factory=lambda: os.getenv(
            "LLM_API_BASE", "https://integrate.api.nvidia.com/v1"
        ).strip()
    )

    nvidia_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("NVIDIA_API_KEY") or None
    )
    openai_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY") or None
    )
    openai_base_url: str = field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
    )
    anthropic_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("ANTHROPIC_AUTH_TOKEN")
        or None
    )
    anthropic_base_url: str = field(
        default_factory=lambda: os.getenv(
            "ANTHROPIC_BASE_URL", "https://api.anthropic.com"
        ).strip()
    )
    ollama_base_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
    )
    ollama_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", "qwen2.5:7b").strip()
    )

    mcp_transport: str = field(
        default_factory=lambda: os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
    )
    mcp_server_command: str = field(
        default_factory=lambda: os.getenv("MCP_SERVER_COMMAND", sys.executable).strip()
    )
    mcp_server_args: str = field(
        default_factory=lambda: os.getenv("MCP_SERVER_ARGS", "mcp_server/server.py").strip()
    )
    mcp_server_cwd: str = field(
        default_factory=lambda: os.getenv(
            "MCP_SERVER_CWD", str(CURRENT_DIR.parent)
        ).strip()
    )
    mcp_server_url: Optional[str] = field(
        default_factory=lambda: os.getenv("MCP_SERVER_URL") or None
    )
    mcp_auth_token: Optional[str] = field(
        default_factory=lambda: os.getenv("MCP_AUTH_TOKEN") or None
    )
    graph_name: str = field(
        default_factory=lambda: (
            os.getenv("GRAPHOS_GRAPH_NAME")
            or os.getenv("FALKORDB_GRAPH")
            or "ALL_GRAPHS"
        ).strip()
    )


    agent_name: str = field(
        default_factory=lambda: os.getenv("AGENT_NAME", "GraphOS Investigator").strip()
    )
    max_iterations: int = field(
        default_factory=lambda: int(os.getenv("AGENT_MAX_ITERATIONS", "10"))
    )
    max_tool_calls: int = field(
        default_factory=lambda: int(os.getenv("AGENT_MAX_TOOL_CALLS", "20"))
    )
    tool_timeout_seconds: int = field(
        default_factory=lambda: int(os.getenv("AGENT_TOOL_TIMEOUT_SECONDS", "30"))
    )
    request_timeout_seconds: int = field(
        default_factory=lambda: int(os.getenv("AGENT_REQUEST_TIMEOUT_SECONDS", "180"))
    )
    max_result_chars: int = field(
        default_factory=lambda: int(os.getenv("AGENT_MAX_RESULT_CHARS", "12000"))
    )

    read_only: bool = field(
        default_factory=lambda: os.getenv("AGENT_READ_ONLY", "true").lower()
        in ("true", "1", "yes")
    )
    allow_action_execution: bool = field(
        default_factory=lambda: os.getenv("AGENT_ALLOW_ACTION_EXECUTION", "false").lower()
        in ("true", "1", "yes")
    )

    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").strip().upper()
    )
    log_tool_calls: bool = field(
        default_factory=lambda: os.getenv("LOG_TOOL_CALLS", "true").lower()
        in ("true", "1", "yes")
    )
    log_redact_secrets: bool = field(
        default_factory=lambda: os.getenv("LOG_REDACT_SECRETS", "true").lower()
        in ("true", "1", "yes")
    )

    def validate_provider_configuration(self) -> None:
        """
        Validate credentials and settings required specifically by the active provider.
        Does not validate unselected providers.
        """
        provider = self.llm_provider
        if provider == "nvidia":
            if not self.nvidia_api_key:
                raise ValueError(
                    "Selected provider is 'nvidia' but NVIDIA_API_KEY is not set. "
                    "Set NVIDIA_API_KEY in agent/.env or switch LLM_PROVIDER."
                )
            if not self.llm_api_base:
                raise ValueError("Selected provider is 'nvidia' but LLM_API_BASE is empty.")

        elif provider == "openai":
            if not self.openai_api_key:
                raise ValueError(
                    "Selected provider is 'openai' but OPENAI_API_KEY is not set. "
                    "Set OPENAI_API_KEY in agent/.env or switch LLM_PROVIDER."
                )

        elif provider == "anthropic":
            if not self.anthropic_api_key:
                raise ValueError(
                    "Selected provider is 'anthropic' but ANTHROPIC_API_KEY is not set. "
                    "Set ANTHROPIC_API_KEY in agent/.env or switch LLM_PROVIDER."
                )

        elif provider == "ollama":
            if not self.ollama_base_url:
                raise ValueError(
                    "Selected provider is 'ollama' but OLLAMA_BASE_URL is empty."
                )

        elif provider == "mock":
            pass

        else:
            raise ValueError(
                f"Unsupported LLM_PROVIDER '{provider}'. "
                "Supported providers: nvidia, openai, anthropic, ollama, mock."
            )

    def masked_diagnostics(self) -> dict[str, Any]:
        """Return non-sensitive diagnostic metadata for startup display."""
        active_key = None
        if self.llm_provider == "nvidia":
            active_key = self.nvidia_api_key
        elif self.llm_provider == "openai":
            active_key = self.openai_api_key
        elif self.llm_provider == "anthropic":
            active_key = self.anthropic_api_key

        return {
            "agent_name": self.agent_name,
            "active_provider": self.llm_provider,
            "active_model": self.llm_model,
            "api_base": self.llm_api_base if self.llm_provider == "nvidia" else (
                self.openai_base_url if self.llm_provider == "openai" else (
                    self.anthropic_base_url if self.llm_provider == "anthropic" else (
                        self.ollama_base_url if self.llm_provider == "ollama" else "mock://local"
                    )
                )
            ),
            "credential_configured": bool(active_key) if self.llm_provider != "mock" else True,
            "credential_masked": mask_secret(active_key) if self.llm_provider != "mock" else "<mock>",
            "mcp_transport": self.mcp_transport,
            "mcp_server": (
                self.mcp_server_url
                if self.mcp_transport == "streamable_http"
                else f"{self.mcp_server_command} {self.mcp_server_args}"
            ),
            "read_only_enforced": self.read_only,
            "max_iterations": self.max_iterations,
            "max_tool_calls": self.max_tool_calls,
        }


settings = AgentSettings()
