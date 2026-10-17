from __future__ import annotations

import asyncio
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from agent.config import AgentSettings, mask_secret, settings as default_settings
from agent.guardrails import MUTATING_TOOLS_BLOCKLIST, READ_ONLY_ALLOWED_TOOLS, GuardrailManager
from agent.mcp_client import MCPClientManager
from agent.providers.factory import get_provider

logger = logging.getLogger("graphos.agent.doctor")


@dataclass
class DiagnosticCheck:
    """A single diagnostic check result."""
    category: str
    name: str
    status: str
    message: str
    remedy: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "remedy": self.remedy,
            "details": self.details,
        }


class GraphOSDoctor:
    """Performs comprehensive system diagnostics, connectivity audits, and configuration validation."""

    def __init__(self, settings: Optional[AgentSettings] = None) -> None:
        self.settings = settings or default_settings

    async def run_diagnostics(self) -> list[DiagnosticCheck]:
        """Execute all diagnostic checks asynchronously and return structured findings."""
        checks: list[DiagnosticCheck] = []

        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        if sys.version_info >= (3, 10):
            checks.append(
                DiagnosticCheck(
                    category="Environment",
                    name="Python Runtime",
                    status="PASS",
                    message=f"Python {py_ver} supported",
                    details={"executable": sys.executable, "version": py_ver},
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    category="Environment",
                    name="Python Runtime",
                    status="FAIL",
                    message=f"Python {py_ver} is unsupported (requires >= 3.10)",
                    remedy="Upgrade to Python 3.10 or higher.",
                )
            )

        packages = ["rich", "prompt_toolkit", "mcp", "httpx", "dotenv"]
        missing_pkgs = []
        for pkg in packages:
            try:
                __import__(pkg)
            except ImportError:
                missing_pkgs.append(pkg)

        if not missing_pkgs:
            checks.append(
                DiagnosticCheck(
                    category="Dependencies",
                    name="Required Packages",
                    status="PASS",
                    message="All core packages installed (rich, prompt_toolkit, mcp, httpx, python-dotenv)",
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    category="Dependencies",
                    name="Required Packages",
                    status="FAIL",
                    message=f"Missing packages: {', '.join(missing_pkgs)}",
                    remedy=f"Run: pip install {' '.join(missing_pkgs)}",
                )
            )

        provider_name = self.settings.llm_provider
        try:
            self.settings.validate_provider_configuration()
            provider_configured = True
        except ValueError as exc:
            provider_configured = False
            checks.append(
                DiagnosticCheck(
                    category="LLM Provider",
                    name=f"Configuration ({provider_name})",
                    status="FAIL",
                    message=str(exc),
                    remedy=f"Configure credentials in agent/.env or pass --provider mock / nvidia / openai / anthropic / ollama",
                )
            )

        if provider_configured:
            try:
                provider = get_provider(self.settings)
                is_ok, msg = await provider.validate_connection()
                if is_ok:
                    checks.append(
                        DiagnosticCheck(
                            category="LLM Provider",
                            name=f"Connectivity ({provider_name.upper()})",
                            status="PASS",
                            message=f"{msg} (model: {self.settings.llm_model})",
                            details=provider.get_model_info(),
                        )
                    )
                else:
                    status = "WARN" if provider_name in ("nvidia", "ollama") else "FAIL"
                    checks.append(
                        DiagnosticCheck(
                            category="LLM Provider",
                            name=f"Connectivity ({provider_name.upper()})",
                            status=status,
                            message=msg,
                            remedy=(
                                "For offline development or tests, use: graphos --provider mock. "
                                "Or update API key in agent/.env."
                            ),
                            details=provider.get_model_info(),
                        )
                    )
            except Exception as exc:
                checks.append(
                    DiagnosticCheck(
                        category="LLM Provider",
                        name=f"Connectivity ({provider_name.upper()})",
                        status="FAIL",
                        message=f"Failed to initialize provider: {exc}",
                        remedy="Check agent/.env settings.",
                    )
                )

        transport = self.settings.mcp_transport
        if transport == "stdio":
            server_file = Path(self.settings.mcp_server_cwd) / self.settings.mcp_server_args.split()[0]
            if server_file.exists():
                checks.append(
                    DiagnosticCheck(
                        category="MCP Server",
                        name="Server Script File",
                        status="PASS",
                        message=f"MCP server script located at {server_file}",
                    )
                )
            else:
                checks.append(
                    DiagnosticCheck(
                        category="MCP Server",
                        name="Server Script File",
                        status="FAIL",
                        message=f"MCP server script not found: {server_file}",
                        remedy="Verify MCP_SERVER_ARGS in agent/.env.",
                    )
                )

        client = MCPClientManager(self.settings)
        try:
            await asyncio.wait_for(client.connect(), timeout=10.0)
            discovered_tools = await client.discover_tools()
            await client.disconnect()

            checks.append(
                DiagnosticCheck(
                    category="MCP Server",
                    name="Session & Tool Discovery",
                    status="PASS",
                    message=f"Connected over {transport}. Discovered {len(discovered_tools)} MCP tools.",
                    details={"tool_count": len(discovered_tools)},
                )
            )

            guard = GuardrailManager(self.settings)
            permitted = guard.filter_available_tools(discovered_tools)
            permitted_names = {t.name for t in permitted}

            leaked_mutators = permitted_names.intersection(MUTATING_TOOLS_BLOCKLIST)
            if not leaked_mutators:
                checks.append(
                    DiagnosticCheck(
                        category="Guardrails",
                        name="Read-Only Safety",
                        status="PASS",
                        message=f"Strict read-only enforcement active: {len(permitted)} tools permitted, 0 mutating tools exposed.",
                        details={"permitted_count": len(permitted)},
                    )
                )
            else:
                checks.append(
                    DiagnosticCheck(
                        category="Guardrails",
                        name="Read-Only Safety",
                        status="FAIL",
                        message=f"CRITICAL: Mutating tools leaked past guardrail: {leaked_mutators}",
                        remedy="Check agent/guardrails.py MUTATING_TOOLS_BLOCKLIST.",
                    )
                )

        except Exception as exc:
            checks.append(
                DiagnosticCheck(
                    category="MCP Server",
                    name="Session & Tool Discovery",
                    status="FAIL",
                    message=f"Failed to connect to MCP server: {type(exc).__name__}: {exc}",
                    remedy="Ensure FalkorDB Cloud credentials and mcp_server/server.py are properly configured.",
                )
            )

        try:
            from agent.session import SessionManager
            sm = SessionManager()
            test_file = sm.storage_dir / ".doctor_test.tmp"
            test_file.write_text("test")
            test_file.unlink()
            checks.append(
                DiagnosticCheck(
                    category="Storage",
                    name="Session Persistence",
                    status="PASS",
                    message=f"Session directory writable: {sm.storage_dir}",
                )
            )
        except Exception as exc:
            checks.append(
                DiagnosticCheck(
                    category="Storage",
                    name="Session Persistence",
                    status="WARN",
                    message=f"Storage directory write error: {exc}",
                    remedy="Verify permissions on ~/.graphos/sessions",
                )
            )

        return checks

    async def get_system_status(self) -> dict[str, Any]:
        """Produce live diagnostic status dictionary for status commands."""
        masked_diag = self.settings.masked_diagnostics()

        provider_ok = False
        provider_msg = "Untested"
        try:
            provider = get_provider(self.settings)
            provider_ok, provider_msg = await provider.validate_connection()
        except Exception as exc:
            provider_msg = str(exc)

        mcp_ok = False
        tool_count = 0
        allowed_count = 0
        try:
            client = MCPClientManager(self.settings)
            await asyncio.wait_for(client.connect(), timeout=8.0)
            tools = await client.discover_tools()
            await client.disconnect()
            mcp_ok = True
            tool_count = len(tools)
            guard = GuardrailManager(self.settings)
            allowed_count = len(guard.filter_available_tools(tools))
        except Exception:
            mcp_ok = False

        status = "Ready" if (provider_ok and mcp_ok) else ("Degraded" if mcp_ok else "Offline")

        return {
            "application_status": status,
            "provider": self.settings.llm_provider,
            "model": self.settings.llm_model,
            "provider_status": "Connected" if provider_ok else f"Warning ({provider_msg[:50]})",
            "mcp_transport": self.settings.mcp_transport,
            "mcp_connection": "Connected" if mcp_ok else "Disconnected",
            "discovered_tools": tool_count,
            "allowed_tools": allowed_count,
            "execution_mode": "Read-Only (Strict Guardrails)" if self.settings.read_only else "Permissive",
            "max_iterations": self.settings.max_iterations,
            "max_tool_calls": self.settings.max_tool_calls,
            "masked_diagnostics": masked_diag,
        }
