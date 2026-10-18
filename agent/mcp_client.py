from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent.config import AgentSettings
from agent.models import ToolDefinition

logger = logging.getLogger("graphos.agent.mcp_client")


class MCPConnectionError(Exception):
    """Raised when connecting to or communicating with the MCP server fails."""


class MCPClientManager:
    """Manages connection, tool discovery, and execution over MCP transports (stdio or HTTP)."""

    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings
        self.transport = settings.mcp_transport
        self.session: Optional[ClientSession] = None
        self._exit_stack = None

    async def connect(self) -> None:
        """Establish connection to the MCP server and initialize session."""
        if self.transport == "stdio":
            cmd = self.settings.mcp_server_command
            if cmd == "python" or cmd == "python3":
                cmd = sys.executable

            args_parts = self.settings.mcp_server_args.split()
            cwd = self.settings.mcp_server_cwd
            cwd_str = str(cwd) if cwd else str(Path(__file__).resolve().parent.parent)

            logger.info(f"Connecting to MCP server via stdio: '{cmd} {' '.join(args_parts)}' (cwd={cwd_str})")

            # Forward parent process environment variables to MCP subprocess so credentials and cloud configs are never lost
            server_env = dict(os.environ)
            if hasattr(self.settings, "falkordb_host") and self.settings.falkordb_host:
                server_env["FALKORDB_HOST"] = str(self.settings.falkordb_host)
            if hasattr(self.settings, "falkordb_port") and self.settings.falkordb_port:
                server_env["FALKORDB_PORT"] = str(self.settings.falkordb_port)
            if hasattr(self.settings, "falkordb_username") and self.settings.falkordb_username:
                server_env["FALKORDB_USERNAME"] = str(self.settings.falkordb_username)
            if hasattr(self.settings, "falkordb_password") and self.settings.falkordb_password:
                server_env["FALKORDB_PASSWORD"] = str(self.settings.falkordb_password)
            if hasattr(self.settings, "falkordb_ssl") and self.settings.falkordb_ssl is not None:
                server_env["FALKORDB_SSL"] = str(self.settings.falkordb_ssl).lower()

            # Ensure PYTHONPATH contains project root
            existing_pp = server_env.get("PYTHONPATH", "")
            server_env["PYTHONPATH"] = f"{cwd_str}:{existing_pp}" if existing_pp else cwd_str

            server_params = StdioServerParameters(
                command=cmd,
                args=args_parts,
                env=server_env,
                cwd=cwd_str,
            )

            self._stdio_ctx = stdio_client(server_params)
            read_stream, write_stream = await self._stdio_ctx.__aenter__()

            self._session_ctx = ClientSession(read_stream, write_stream)
            self.session = await self._session_ctx.__aenter__()

            await self.session.initialize()
            logger.info("MCP Session successfully initialized over stdio.")

        elif self.transport in ("streamable_http", "sse", "http"):
            server_url = self.settings.mcp_server_url
            if not server_url:
                raise MCPConnectionError("MCP_TRANSPORT is HTTP/SSE but MCP_SERVER_URL is not configured.")

            from mcp.client.sse import sse_client
            logger.info(f"Connecting to MCP server via SSE: {server_url}")
            headers = {}
            if self.settings.mcp_auth_token:
                headers["Authorization"] = f"Bearer {self.settings.mcp_auth_token}"

            self._sse_ctx = sse_client(server_url, headers=headers)
            read_stream, write_stream = await self._sse_ctx.__aenter__()

            self._session_ctx = ClientSession(read_stream, write_stream)
            self.session = await self._session_ctx.__aenter__()
            await self.session.initialize()
            logger.info("MCP Session successfully initialized over SSE/HTTP.")

        else:
            raise MCPConnectionError(f"Unsupported MCP_TRANSPORT '{self.transport}'. Supported: stdio, streamable_http.")

    async def disconnect(self) -> None:
        """Cleanly close MCP session and process streams."""
        try:
            if hasattr(self, "_session_ctx") and self._session_ctx:
                await self._session_ctx.__aexit__(None, None, None)
            if hasattr(self, "_stdio_ctx") and self._stdio_ctx:
                await self._stdio_ctx.__aexit__(None, None, None)
            if hasattr(self, "_sse_ctx") and self._sse_ctx:
                await self._sse_ctx.__aexit__(None, None, None)
            logger.info("MCP client disconnected cleanly.")
        except (Exception, asyncio.CancelledError, BaseException) as exc:
            logger.debug(f"Error during MCP disconnect: {exc}")
        finally:
            self.session = None

    async def discover_tools(self) -> list[ToolDefinition]:
        """Dynamically query the MCP server for available tools and their input schemas."""
        if not self.session:
            raise MCPConnectionError("MCP client is not connected. Call connect() first.")

        try:
            tools_response = await self.session.list_tools()
            discovered: list[ToolDefinition] = []

            for t in tools_response.tools:
                schema = getattr(t, "input_schema", getattr(t, "inputSchema", {}))
                discovered.append(
                    ToolDefinition(
                        name=t.name,
                        description=t.description or f"Tool {t.name}",
                        parameters=schema if isinstance(schema, dict) else {},
                    )
                )


            logger.info(f"Discovered {len(discovered)} tools from active MCP server.")
            return discovered
        except Exception as exc:
            raise MCPConnectionError(f"Failed to list tools from MCP server: {exc}") from exc

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool through the active MCP session with timeout enforcement."""
        if not self.session:
            raise MCPConnectionError("MCP client is not connected.")

        timeout = self.settings.tool_timeout_seconds
        try:
            res = await asyncio.wait_for(
                self.session.call_tool(name, arguments=arguments),
                timeout=timeout,
            )

            output_parts = []
            for block in res.content:
                text_val = getattr(block, "text", None)
                if text_val is not None:
                    output_parts.append(str(text_val))
                else:
                    output_parts.append(str(block))

            return "\n".join(output_parts)

        except asyncio.TimeoutError:
            err_msg = f"ERROR: MCP tool call to '{name}' timed out after {timeout} seconds."
            logger.error(err_msg)
            return json.dumps({"error": err_msg, "tool": name, "timeout": True})
        except Exception as exc:
            err_msg = f"ERROR: MCP tool call to '{name}' failed: {type(exc).__name__}: {exc}"
            logger.error(err_msg)
            return json.dumps({"error": err_msg, "tool": name, "success": False})

    async def __aenter__(self) -> MCPClientManager:
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.disconnect()
