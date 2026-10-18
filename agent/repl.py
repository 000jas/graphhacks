from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style

from agent.config import AgentSettings, settings as default_settings
from agent.doctor import GraphOSDoctor
from agent.engine import GraphOSInvestigator
from agent.mcp_client import MCPClientManager
from agent.providers.factory import get_provider
from agent.session import SessionManager
from agent.ui import TerminalUI

SLASH_COMMANDS = [
    "/help",
    "/status",
    "/doctor",
    "/config",
    "/tools",
    "/model",
    "/graph",
    "/graphs",
    "/schema",
    "/refresh",
    "/history",
    "/new",
    "/reset",
    "/clear",
    "/exit",
    "/quit",
]


class InteractiveREPL:
    """
    Polished, stateful, multi-turn interactive terminal REPL inspired by
    OpenCode and Claude Code.
    """

    def __init__(
        self,
        settings: Optional[AgentSettings] = None,
        investigator: Optional[GraphOSInvestigator] = None,
        session_manager: Optional[SessionManager] = None,
        ui: Optional[TerminalUI] = None,
    ) -> None:
        self.settings = settings or default_settings
        self.ui = ui or TerminalUI()
        self.session_manager = session_manager or SessionManager(
            provider=self.settings.llm_provider,
            model=self.settings.llm_model,
        )
        self.investigator = investigator or GraphOSInvestigator(settings=self.settings)
        self.doctor = GraphOSDoctor(self.settings)

        hist_dir = Path.home() / ".graphos"
        hist_dir.mkdir(parents=True, exist_ok=True)
        hist_file = hist_dir / "history"

        completer = WordCompleter(SLASH_COMMANDS, ignore_case=True, sentence=True)

        prompt_style = Style.from_dict({
            "brand": "bold #38bdf8",
            "arrow": "bold #4ade80",
        })

        self.prompt_session = PromptSession(
            history=FileHistory(str(hist_file)),
            completer=completer,
            style=prompt_style,
        )

    async def run(self) -> int:
        """Main REPL loop."""
        status_info = await self.doctor.get_system_status()
        self.ui.print_banner({
            "provider": self.settings.llm_provider,
            "model": self.settings.llm_model,
            "graph_status": "FalkorDB Cloud (Connected)" if status_info["mcp_connection"] == "Connected" else "FalkorDB (Checking...)",
            "allowed_tools": status_info.get("allowed_tools", 31),
            "discovered_tools": status_info.get("discovered_tools", 36),
        })

        while True:
            try:
                prompt_text = HTML("<brand>graphos</brand> <arrow>❯</arrow> ")
                user_input = await self.prompt_session.prompt_async(prompt_text)
                user_input = user_input.strip()

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    should_exit = await self._handle_slash_command(user_input)
                    if should_exit:
                        break
                    continue

                await self._execute_investigation_turn(user_input)

            except (KeyboardInterrupt, asyncio.CancelledError):
                self.ui.console.print("\n[dim]Input cancelled.[/dim]")
                continue
            except EOFError:
                self.ui.console.print("\n[bold cyan]Goodbye from GraphOS.[/bold cyan]")
                break
            except Exception as exc:
                self.ui.console.print(f"\n[bold red]Error in REPL session:[/bold red] {exc}\n")
                continue

        return 0

    async def _handle_slash_command(self, cmd_line: str) -> bool:
        """Process slash commands. Returns True if REPL should exit."""
        parts = cmd_line.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ("/exit", "/quit"):
            self.ui.console.print("[bold cyan]Session concluded. Goodbye from GraphOS.[/bold cyan]")
            return True

        elif cmd == "/help":
            self.ui.render_help()

        elif cmd == "/schema":
            self.ui.console.print("  [dim]Discovering connected runtime graph schema via MCP...[/dim]")
            try:
                profile = await self.investigator.get_runtime_schema(force_refresh=False)
                self.ui.render_schema(profile)
            except Exception as exc:
                self.ui.console.print(f"[bold red]Failed to inspect schema:[/bold red] {exc}")

        elif cmd == "/graph":
            if not args:
                self.ui.console.print(
                    f"  [bold white]Active Graph Target:[/bold white] [cyan]{self.settings.graph_name}[/cyan]\n"
                    "  [dim]Usage: /graph <graph_name>[/dim]\n"
                    "  [dim]Example: /graph swiftpay_unified[/dim]\n"
                    "  [dim]Use /graphs to list all available database graphs[/dim]\n"
                )
            else:
                new_graph = args[0].strip()
                self.settings.graph_name = new_graph
                self.investigator.schema_manager.invalidate()
                self.ui.console.print(
                    f"  [bold green]✓ Switched active graph to '{new_graph}'[/bold green] (Schema cache invalidated)\n"
                )

        elif cmd == "/graphs":
            self.ui.console.print("  [dim]Querying available graphs in FalkorDB Cloud...[/dim]")
            try:
                from mcp_server.db import get_db_client
                client = get_db_client()
                avail_graphs = client.list_graphs()
                self.ui.console.print(f"  [bold white]Available FalkorDB Graphs ({len(avail_graphs)}):[/bold white]")
                for g in avail_graphs:
                    is_active = " [bold green](active)[/bold green]" if g == self.settings.graph_name else ""
                    self.ui.console.print(f"    • [cyan]{g}[/cyan]{is_active}")
                self.ui.console.print("  [dim]Switch active graph with: /graph <name>[/dim]\n")
            except Exception as exc:
                self.ui.console.print(f"[bold red]Failed to list graphs:[/bold red] {exc}")

        elif cmd == "/refresh":
            self.ui.console.print("  [dim]Forcing dynamic re-discovery of graph schema from FalkorDB...[/dim]")
            try:
                profile = await self.investigator.get_runtime_schema(force_refresh=True)
                self.ui.render_schema(profile)
            except Exception as exc:
                self.ui.console.print(f"[bold red]Failed to refresh schema:[/bold red] {exc}")

        elif cmd == "/status":
            self.ui.console.print("  [dim]Auditing system connections...[/dim]")
            status_data = await self.doctor.get_system_status()
            self.ui.render_status(status_data)

        elif cmd == "/doctor":
            self.ui.console.print("  [dim]Running comprehensive system diagnostics...[/dim]")
            checks = await self.doctor.run_diagnostics()
            self.ui.render_doctor(checks)

        elif cmd == "/config":
            self.ui.render_config(self.settings.masked_diagnostics())

        elif cmd == "/tools":
            self.ui.console.print("  [dim]Discovering tools via MCP server...[/dim]")
            try:
                async with MCPClientManager(self.settings) as client:
                    raw_tools = await client.discover_tools()
                permitted = self.investigator.guardrails.filter_available_tools(raw_tools)
                self.ui.render_tools(permitted)
            except Exception as exc:
                self.ui.console.print(f"[bold red]Failed to discover tools:[/bold red] {exc}")

        elif cmd == "/model":
            if not args:
                self.ui.console.print(
                    f"  [bold white]Current Provider:[/bold white] [cyan]{self.settings.llm_provider.upper()}[/cyan]\n"
                    f"  [bold white]Current Model:[/bold white]    [cyan]{self.settings.llm_model}[/cyan]\n"
                    "  [dim]Usage: /model <provider> [model_name][/dim]\n"
                    "  [dim]Example: /model mock[/dim]\n"
                    "  [dim]Example: /model openai gpt-4o[/dim]\n"
                )
            else:
                new_prov = args[0].lower()
                new_model = args[1] if len(args) > 1 else self.settings.llm_model
                old_prov = self.settings.llm_provider
                self.settings.llm_provider = new_prov
                if len(args) > 1:
                    self.settings.llm_model = new_model

                try:
                    self.settings.validate_provider_configuration()
                    self.investigator.provider = get_provider(self.settings)
                    ok, msg = await self.investigator.provider.validate_connection()
                    if ok:
                        self.ui.console.print(
                            f"  [bold green]✓ Switched provider to {new_prov.upper()} ({self.settings.llm_model})[/bold green]\n"
                        )
                    else:
                        self.ui.console.print(
                            f"  [bold yellow]⚠️ Switched to {new_prov.upper()} with warning:[/bold yellow] {msg}\n"
                        )
                except Exception as exc:
                    self.settings.llm_provider = old_prov
                    self.ui.console.print(f"  [bold red]Failed to switch provider:[/bold red] {exc}\n")

        elif cmd in ("/new", "/reset"):
            new_id = self.session_manager.new_session(
                provider=self.settings.llm_provider,
                model=self.settings.llm_model,
            )
            self.ui.console.print(
                f"  [bold green]✓ Started fresh investigation session (ID: {new_id})[/bold green]\n"
            )

        elif cmd == "/history":
            self.ui.render_history(self.session_manager.state.turns)

        elif cmd == "/clear":
            self.ui.console.clear()
            status_info = await self.doctor.get_system_status()
            self.ui.print_banner({
                "provider": self.settings.llm_provider,
                "model": self.settings.llm_model,
                "graph_status": "FalkorDB Cloud (Connected)" if status_info["mcp_connection"] == "Connected" else "FalkorDB",
                "allowed_tools": status_info.get("allowed_tools", 31),
                "discovered_tools": status_info.get("discovered_tools", 36),
            })

        else:
            self.ui.console.print(
                f"  [bold yellow]Unknown command:[/bold yellow] '{cmd}'. Type [bold cyan]/help[/bold cyan] for available commands.\n"
            )

        return False

    async def _execute_investigation_turn(self, query: str) -> None:
        """Run an investigation with conversation context and handle Ctrl+C cancellation."""
        self.ui.console.print()

        context = self.session_manager.get_conversation_context(max_turns=3)

        investigation_task = asyncio.create_task(
            self.investigator.investigate(
                objective=query,
                on_event_callback=self.ui.render_event,
                conversation_context=context,
            )
        )

        try:
            result = await investigation_task
            self.ui.render_final_report(result)
            self.session_manager.add_turn(query, result)
        except (KeyboardInterrupt, asyncio.CancelledError):
            investigation_task.cancel()
            self.ui.console.print(
                "\n  [bold yellow]⚡ Investigation interrupted by user (Ctrl+C). Ready for next query.[/bold yellow]\n"
            )
        except Exception as exc:
            self.ui.console.print(
                f"\n  [bold red]❌ Investigation failed:[/bold red] {type(exc).__name__}: {exc}\n"
            )
