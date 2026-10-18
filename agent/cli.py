from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.config import settings
from agent.doctor import GraphOSDoctor
from agent.engine import GraphOSInvestigator
from agent.mcp_client import MCPClientManager
from agent.repl import InteractiveREPL
from agent.session import SessionManager
from agent.ui import TerminalUI

__version__ = "0.2.0"


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    chatty_loggers = [
        "httpx",
        "httpcore",
        "falkordb",
        "asyncio",
        "graphos.agent.engine",
        "graphos.agent.mcp_client",
        "graphos.agent.schema_context",
        "graphos.agent.guardrails",
    ]
    for name in chatty_loggers:
        logging.getLogger(name).setLevel(logging.DEBUG if verbose else logging.WARNING)


async def execute_oneshot_investigation(
    query: str,
    ui: TerminalUI,
    json_mode: bool = False,
    quiet: bool = False,
) -> int:
    """Execute a single query against FalkorDB via MCP and print report or JSON."""
    try:
        settings.validate_provider_configuration()
    except ValueError as exc:
        if json_mode:
            print(json.dumps({"success": False, "error": str(exc)}, indent=2))
        else:
            ui.console.print(f"\n[bold red]Configuration Error:[/bold red] {exc}\n")
            ui.console.print("[dim]Hint: Set credentials in .env or pass --provider mock / nvidia / openai[/dim]\n")
        return 1

    investigator = GraphOSInvestigator(settings=settings)

    if not json_mode and not quiet:
        is_ok, msg = await investigator.provider.validate_connection()
        if not is_ok:
            ui.console.print(f"  [bold yellow]⚠️ Provider warning:[/bold yellow] [dim]{msg}[/dim]")
            if settings.llm_provider == "nvidia":
                ui.console.print("  [dim](To run an offline or hermetic demonstration, use: graphos --provider mock)[/dim]\n")

    try:
        result = await investigator.investigate(
            objective=query,
            on_event_callback=ui.render_event if not (json_mode or quiet) else None,
        )

        if json_mode:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            ui.render_final_report(result)

        try:
            sm = SessionManager(provider=settings.llm_provider, model=settings.llm_model)
            sm.add_turn(query, result)
        except Exception:
            pass

        if not json_mode and not quiet and sys.stdin.isatty():
            try:
                import re
                ui.console.print("[bold cyan]👉 Interactive Next Step:[/bold cyan] Choose [bold white][1-3][/bold white], ask a follow-up, or press [bold white]Enter[/bold white] to finish: ", end="")
                user_choice = input().strip()
                if user_choice:
                    next_query = user_choice
                    if user_choice in ("1", "2", "3"):
                        actions = re.findall(rf"\[{user_choice}\]\s*(.+)", result.final_answer)
                        if actions:
                            next_query = actions[0].strip()
                    ui.console.print(f"\n[bold green]◈ Investigating follow-up:[/bold green] [white]{next_query}[/white]\n")
                    from agent.models import ChatMessage
                    conv_context = [
                        ChatMessage(role="user", content=query),
                        ChatMessage(role="assistant", content=result.final_answer),
                    ]
                    followup_result = await investigator.investigate(
                        objective=next_query,
                        on_event_callback=ui.render_event,
                        conversation_context=conv_context,
                    )
                    ui.render_final_report(followup_result)
            except (KeyboardInterrupt, EOFError):
                pass

        return 0

    except Exception as exc:
        if json_mode:
            print(json.dumps({"success": False, "error": f"{type(exc).__name__}: {exc}"}, indent=2))
        else:
            ui.console.print(f"\n[bold red]❌ Investigation failed:[/bold red] {type(exc).__name__}: {exc}\n")
        return 1


async def async_main(args: argparse.Namespace) -> int:
    setup_logging(args.verbose, args.quiet or getattr(args, "json", False))

    if getattr(args, "provider", None):
        settings.llm_provider = args.provider.strip().lower()
    if getattr(args, "model", None):
        settings.llm_model = args.model.strip()
    if getattr(args, "graph", None):
        settings.graph_name = args.graph.strip()
    if getattr(args, "max_iterations", None):
        settings.max_iterations = int(args.max_iterations)

    no_color = getattr(args, "no_color", False)
    quiet = getattr(args, "quiet", False)
    verbose = getattr(args, "verbose", False)
    json_mode = getattr(args, "json", False)

    ui = TerminalUI(no_color=no_color, quiet=quiet, verbose=verbose)
    doctor = GraphOSDoctor(settings)

    command = getattr(args, "subcommand", None)

    if command == "status":
        status_data = await doctor.get_system_status()
        if json_mode:
            print(json.dumps(status_data, indent=2))
        else:
            ui.render_status(status_data)
        return 0

    elif command == "doctor":
        checks = await doctor.run_diagnostics()
        if json_mode:
            print(json.dumps([c.to_dict() for c in checks], indent=2))
        else:
            ui.render_doctor(checks)
        has_failures = any(c.status == "FAIL" for c in checks)
        return 1 if has_failures else 0

    elif command == "config":
        diag = settings.masked_diagnostics()
        if json_mode:
            print(json.dumps(diag, indent=2))
        else:
            ui.render_config(diag)
        return 0

    elif command == "tools":
        try:
            async with MCPClientManager(settings) as client:
                raw_tools = await client.discover_tools()
            guard = GraphOSInvestigator(settings=settings).guardrails
            permitted = guard.filter_available_tools(raw_tools)
            if json_mode:
                tools_data = [
                    {"name": t.name, "description": t.description, "parameters": t.parameters}
                    for t in permitted
                ]
                print(json.dumps(tools_data, indent=2))
            else:
                ui.render_tools(permitted)
            return 0
        except Exception as exc:
            if json_mode:
                print(json.dumps({"error": str(exc)}, indent=2))
            else:
                ui.console.print(f"[bold red]Failed to discover tools:[/bold red] {exc}")
            return 1

    elif command in ("schema", "graph"):
        investigator = GraphOSInvestigator(settings=settings)
        try:
            profile = await investigator.get_runtime_schema(force_refresh=False)
            if json_mode:
                print(json.dumps(profile.to_summary_dict(), indent=2))
            else:
                ui.render_schema(profile)
            return 0
        except Exception as exc:
            if json_mode:
                print(json.dumps({"error": str(exc)}, indent=2))
            else:
                ui.console.print(f"[bold red]Failed to discover schema:[/bold red] {exc}")
            return 1
        finally:
            await investigator.mcp_client.disconnect()

    elif command == "refresh":
        investigator = GraphOSInvestigator(settings=settings)
        try:
            profile = await investigator.get_runtime_schema(force_refresh=True)
            if json_mode:
                print(json.dumps(profile.to_summary_dict(), indent=2))
            else:
                ui.render_schema(profile)
            return 0
        except Exception as exc:
            if json_mode:
                print(json.dumps({"error": str(exc)}, indent=2))
            else:
                ui.console.print(f"[bold red]Failed to refresh schema:[/bold red] {exc}")
            return 1
        finally:
            await investigator.mcp_client.disconnect()

    elif command == "ask":
        query = args.query.strip()
        if not query:
            ui.console.print("[bold red]Error: Query string must not be empty.[/bold red]")
            return 1
        return await execute_oneshot_investigation(query, ui, json_mode=json_mode, quiet=quiet)

    query = getattr(args, "query", None)
    if query:
        return await execute_oneshot_investigation(query.strip(), ui, json_mode=json_mode, quiet=quiet)

    repl = InteractiveREPL(settings=settings, ui=ui)
    return await repl.run()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="graphos",
        description="GraphOS — Evidence-Bound Graph AI Agent (CLI-First Interactive Terminal Agent)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  graphos                                 Start interactive investigation session\n"
            "  graphos ask \"Why is payments delayed?\" One-shot investigation\n"
            "  graphos ask \"...\" --json                Emit machine-readable JSON report\n"
            "  graphos status                          Live connection and tool status\n"
            "  graphos doctor                          Comprehensive health & diagnostic check\n"
            "  graphos config                          Display safe runtime configuration\n"
            "  graphos tools                           Catalog discovered read-only MCP tools\n"
            "  graphos --provider mock                 Run offline hermetic demonstration\n"
        ),
    )

    parser.add_argument("-v", "--version", action="version", version=f"graphos {__version__}")
    parser.add_argument("-q", "--query", type=str, help="Execute a one-shot investigation query")
    parser.add_argument("-g", "--graph", type=str, help="Override target FalkorDB graph (e.g. swiftpay_unified, graphos_dev)")
    parser.add_argument("--provider", type=str, choices=["nvidia", "openai", "anthropic", "ollama", "mock"], help="Override active LLM provider")
    parser.add_argument("--model", type=str, help="Override LLM model identifier")
    parser.add_argument("--max-iterations", type=int, help="Override maximum iteration budget")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress streaming")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logs")
    parser.add_argument("--no-color", action="store_true", help="Disable rich terminal colors")

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    ask_parser = subparsers.add_parser("ask", help="Execute a one-shot investigation query")
    ask_parser.add_argument("query", type=str, help="Investigation question or objective")
    ask_parser.add_argument("-g", "--graph", type=str, default=argparse.SUPPRESS, help="Override target FalkorDB graph")
    ask_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    ask_parser.add_argument("--quiet", action="store_true", help="Suppress intermediate streaming")
    ask_parser.add_argument("--provider", type=str, choices=["nvidia", "openai", "anthropic", "ollama", "mock"], default=argparse.SUPPRESS, help="Override provider")
    ask_parser.add_argument("--model", type=str, default=argparse.SUPPRESS, help="Override model identifier")
    ask_parser.add_argument("--max-iterations", type=int, default=argparse.SUPPRESS, help="Override maximum iterations")

    status_parser = subparsers.add_parser("status", help="Live status of provider, FalkorDB, and MCP server")
    status_parser.add_argument("-g", "--graph", type=str, default=argparse.SUPPRESS, help="Override target FalkorDB graph")
    status_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    doctor_parser = subparsers.add_parser("doctor", help="Run comprehensive diagnostics and troubleshooting checks")
    doctor_parser.add_argument("-g", "--graph", type=str, default=argparse.SUPPRESS, help="Override target FalkorDB graph")
    doctor_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    config_parser = subparsers.add_parser("config", help="Display safe configuration settings with secrets masked")
    config_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    tools_parser = subparsers.add_parser("tools", help="List discovered read-only MCP tools")
    tools_parser.add_argument("-g", "--graph", type=str, default=argparse.SUPPRESS, help="Override target FalkorDB graph")
    tools_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    schema_parser = subparsers.add_parser("schema", help="Inspect discovered runtime graph schema and topological properties")
    schema_parser.add_argument("-g", "--graph", type=str, default=argparse.SUPPRESS, help="Override target FalkorDB graph")
    schema_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    refresh_parser = subparsers.add_parser("refresh", help="Force dynamic re-discovery of graph schema from FalkorDB")
    refresh_parser.add_argument("-g", "--graph", type=str, default=argparse.SUPPRESS, help="Override target FalkorDB graph")
    refresh_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    subparsers.add_parser("repl", help="Start the interactive terminal REPL")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    code = asyncio.run(async_main(args))
    sys.exit(code)


if __name__ == "__main__":
    main()
