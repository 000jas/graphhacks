from __future__ import annotations

import json
import os
import sys
from typing import Any, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agent.models import AgentResult, InvestigationEvent, ToolDefinition


BANNER_ASCII = r"""
  ██████╗ ██████╗  █████╗ ██████╗ ██╗  ██╗ ██████╗ ███████╗
 ██╔════╝ ██╔══██╗██╔══██╗██╔═══██╗██║  ██║██╔═══██╗██╔════╝
 ██║  ███╗██████╔╝███████║██████╔╝ ███████║██║   ██║███████╗
 ██║   ██║██╔══██╗██╔══██║██╔═══╝  ██╔══██║██║   ██║╚════██║
 ╚██████╔╝██║  ██║██║  ██║██║     ██║  ██║╚██████╔╝███████║
  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
"""


class TerminalUI:
    """Renders polished terminal outputs, banners, status tables, and evidence reports."""

    def __init__(self, no_color: bool = False, quiet: bool = False, verbose: bool = False) -> None:
        self.no_color = no_color or os.getenv("NO_COLOR", "").lower() in ("1", "true")
        self.quiet = quiet
        self.verbose = verbose
        self.console = Console(no_color=self.no_color, highlight=False)

    def print_banner(self, status_info: dict[str, Any]) -> None:
        """Display the GraphOS startup banner with live connection metadata."""
        if self.quiet:
            return

        provider = str(status_info.get("provider", "NVIDIA")).upper()
        model = str(status_info.get("model", "openai/gpt-oss-20b"))
        graph_status = str(status_info.get("graph_status", "FalkorDB Cloud"))
        tool_count = status_info.get("allowed_tools", "MCP")
        total_tools = status_info.get("discovered_tools", 0)

        tools_display = f"MCP ({tool_count} read-only / {total_tools} discovered)" if total_tools else "MCP (Read-Only)"

        self.console.print(f"[bold cyan]{BANNER_ASCII}[/bold cyan]")
        self.console.print("  [bold white]Connected-data intelligence from the terminal.[/bold white]\n")

        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold dim", justify="left")
        grid.add_column(style="white", justify="left")

        grid.add_row("Model", f"{provider} · {model}")
        grid.add_row("Graph", f"{graph_status}")
        grid.add_row("Tools", f"{tools_display}")
        grid.add_row("Mode", "[bold yellow]READ ONLY[/bold yellow] (Strict Guardrails)")

        self.console.print(Panel(grid, border_style="dim", expand=False))
        self.console.print("  Type [bold cyan]/help[/bold cyan] to see commands.\n")

    def render_event(self, event: InvestigationEvent) -> None:
        """Stream real-time investigation events to the terminal."""
        if self.quiet:
            return

        etype = event.event_type
        if etype == "plan":
            self.console.print(f"  [bold cyan]◈[/bold cyan] {event.message}")
        elif etype == "thought":
            if self.verbose:
                thought_preview = event.message.strip().replace("\n", " ")
                self.console.print(f"  [dim]💭 Thought: {thought_preview}[/dim]")
        elif etype == "tool_call":
            tool_name = event.metadata.get("tool", "")
            args = event.metadata.get("arguments", {})
            args_summary = ", ".join(f"{k}='{v}'" if isinstance(v, str) and len(v) < 25 else f"{k}={v}" for k, v in list(args.items())[:3])
            self.console.print(f"  [bold cyan]◈[/bold cyan] Calling MCP tool: [bold white]{tool_name}[/bold white] [dim]({args_summary})[/dim]")
        elif etype == "tool_result":
            tool_name = event.metadata.get("tool", "")
            length = event.metadata.get("output_length", 0)
            self.console.print(f"  [bold green]◈[/bold green] [dim]Retrieved data from {tool_name} ({length} bytes)[/dim]")
        elif etype == "guardrail_blocked":
            reason = event.metadata.get("reason", event.message)
            self.console.print(f"  [bold yellow]⚠️  Guardrail enforced:[/bold yellow] [dim]{reason}[/dim]")
        elif etype == "limit_reached":
            self.console.print(f"  [bold yellow]⚠️  {event.message}[/bold yellow]")
        elif etype == "complete":
            self.console.print(f"  [bold green]✓[/bold green] [bold white]{event.message}[/bold white]\n")
        elif etype == "info":
            if self.verbose:
                self.console.print(f"  [dim]ℹ {event.message}[/dim]")

    def render_final_report(self, result: AgentResult) -> None:
        """Render the grounded investigation report cleanly with simple reasoning and interactive options."""
        self.console.print()
        self.console.print(Markdown(result.final_answer))
        self.console.print()

        summary = result.evidence_summary or {}
        entities = summary.get("entities") or {}
        key_paths = summary.get("key_paths") or []

        if key_paths:
            path_lines = []
            for p in list(key_paths)[:3]:
                chain = " ➔ ".join(p.get("chain_names", [])) or " ➔ ".join(p.get("relationships", []))
                if chain:
                    path_lines.append(f"  • [bold white]{p.get('source_id', '')}[/bold white] ➔ [cyan]{chain}[/cyan]")
            if path_lines:
                self.console.print(
                    Panel(
                        "\n".join(path_lines),
                        title="[bold cyan]🔗 Verified Dependency Chain[/bold cyan]",
                        border_style="cyan dim",
                        expand=False,
                    )
                )
                self.console.print()

        dur = result.duration_seconds
        calls = result.total_tool_calls
        ent_count = summary.get("total_entities_verified", len(entities))
        prov_name = (result.provider_info or {}).get("provider", "LLM")
        model_name = (result.provider_info or {}).get("model", "")
        self.console.print(
            f"  [dim]⚡ Verified in {dur}s · {calls} tool calls · {ent_count} entities grounded · {prov_name} ({model_name})[/dim]\n"
        )

    def render_help(self) -> None:
        """Display help panel with available slash commands and usage guidance."""
        table = Table(
            border_style="dim",
            header_style="bold cyan",
            expand=False,
            title="GraphOS Interactive Shell Commands",
            title_style="bold white",
        )
        table.add_column("Command", style="bold cyan")
        table.add_column("Description", style="white")

        table.add_row("/help", "Show this help reference")
        table.add_row("/schema, /graph", "Inspect discovered runtime graph schema, entity classes, relationships, and property catalog")
        table.add_row("/refresh", "Force dynamic re-discovery of graph schema from connected FalkorDB instance")
        table.add_row("/status", "Display live system status, provider, FalkorDB, and tool discovery")
        table.add_row("/doctor", "Perform deep diagnostic health checks across all components")
        table.add_row("/config", "Show safe runtime configuration with credentials redacted")
        table.add_row("/tools", "List discovered read-only MCP tools and schema parameters")
        table.add_row("/model [provider] [model]", "Inspect or switch active LLM provider and model")
        table.add_row("/history", "View conversational turns and metrics in current session")
        table.add_row("/new, /reset", "Clear context and start a fresh investigation session")
        table.add_row("/clear", "Clear the terminal screen and redisplay banner")
        table.add_row("/exit, /quit", "Leave the interactive session cleanly (or press Ctrl+D)")

        self.console.print(table)
        self.console.print("\n[bold dim]Tips:[/bold dim]")
        self.console.print("  • Ask questions in natural language: [white]Investigate dependencies affecting this component[/white]")
        self.console.print("  • Discover graph structure: [white]What kinds of data are in this graph?[/white]")
        self.console.print("  • Trace connections: [white]Explain how these two entities are connected[/white]")
        self.console.print("  • Press [bold white]Ctrl+C[/bold white] to interrupt an ongoing investigation without quitting.")
        self.console.print()

    def render_schema(self, profile: Any) -> None:
        """Display discovered runtime graph schema profile and topological statistics."""
        data = profile.to_summary_dict() if hasattr(profile, "to_summary_dict") else profile

        title = f"Runtime Graph Profile: {data.get('graph_identity', 'default')}"
        domain = data.get("inferred_domain", "Connected Knowledge Graph")
        nodes = data.get("total_nodes", 0)
        edges = data.get("total_edges", 0)
        density = data.get("density", 0.0)
        avg_deg = data.get("average_degree", 0.0)

        summary_text = (
            f"[bold cyan]Domain Profile:[/bold cyan] {domain}\n"
            f"[bold cyan]Topology:[/bold cyan] {nodes} nodes, {edges} relationships | "
            f"Density: {density} | Avg Degree: {avg_deg}"
        )
        self.console.print(Panel(summary_text, title=f"📊 [bold white]{title}[/bold white]", border_style="cyan"))

        kinds = data.get("node_kinds", [])
        if kinds:
            k_table = Table(
                title="Discovered Entity Kinds / Labels",
                border_style="dim",
                header_style="bold cyan",
                expand=False,
            )
            k_table.add_column("Entity Kind / Label", style="bold white")
            k_table.add_column("Observed Node Count", justify="right", style="cyan")

            for k in kinds[:15]:
                k_table.add_row(k.get("kind", "Unknown"), str(k.get("count", 0)))
            self.console.print(k_table)
            self.console.print()

        rel_types = data.get("relationship_types", [])
        if rel_types:
            r_table = Table(
                title="Discovered Relationship Types",
                border_style="dim",
                header_style="bold cyan",
                expand=False,
            )
            r_table.add_column("Relationship Type", style="bold white")
            r_table.add_column("Total Instances", justify="right", style="cyan")

            for r in rel_types[:15]:
                r_table.add_row(r.get("type", "Unknown"), str(r.get("total_instances", 0)))
            self.console.print(r_table)
            self.console.print()

        patterns = data.get("relationship_patterns", [])
        if patterns:
            p_table = Table(
                title="Observed Connection Patterns",
                border_style="dim",
                header_style="bold dim",
                expand=False,
            )
            p_table.add_column("Source Kind", style="cyan")
            p_table.add_column("Relationship", style="bold white", justify="center")
            p_table.add_column("Target Kind", style="cyan")
            p_table.add_column("Instances", justify="right", style="dim")

            for p in patterns[:12]:
                p_table.add_row(
                    p.get("source_kind", "Node"),
                    f"-[{p.get('relationship_type', 'REL')}]->",
                    p.get("target_kind", "Node"),
                    str(p.get("count", 0)),
                )
            self.console.print(p_table)
            self.console.print()

        limitations = data.get("limitations", [])
        if limitations:
            self.console.print("[bold yellow]⚠️ Known Graph Limitations / Anomalies:[/bold yellow]")
            for lim in limitations:
                self.console.print(f"  • {lim}")
            self.console.print()

    def render_status(self, status: dict[str, Any]) -> None:
        """Display live system status table."""
        app_status = status.get("application_status", "Ready")
        style = "bold green" if app_status == "Ready" else "bold yellow"

        table = Table(
            title=f"GraphOS System Status — [{style}]{app_status}[/{style}]",
            border_style="dim",
            header_style="bold dim",
            expand=False,
        )
        table.add_column("Component", style="bold white")
        table.add_column("Runtime Value", style="cyan")

        table.add_row("Provider", status.get("provider", "").upper())
        table.add_row("Model", status.get("model", ""))
        table.add_row("Provider Status", status.get("provider_status", "Untested"))
        table.add_row("MCP Transport", status.get("mcp_transport", "stdio"))
        table.add_row("MCP Connection", status.get("mcp_connection", "Disconnected"))
        table.add_row("Discovered Tools", str(status.get("discovered_tools", 0)))
        table.add_row("Allowed Tools", str(status.get("allowed_tools", 0)))
        table.add_row("Execution Mode", status.get("execution_mode", "Read-Only"))
        table.add_row("Max Iterations", str(status.get("max_iterations", 10)))
        table.add_row("Max Tool Calls", str(status.get("max_tool_calls", 20)))

        self.console.print(table)
        self.console.print()

    def render_doctor(self, checks: list[Any]) -> None:
        """Display diagnostic health check audit table."""
        table = Table(
            title="GraphOS Doctor Diagnostic Audit",
            border_style="dim",
            header_style="bold dim",
            expand=False,
        )
        table.add_column("Category", style="dim")
        table.add_column("Check", style="bold white")
        table.add_column("Status", justify="center")
        table.add_column("Message", style="white")

        for c in checks:
            badge = "[bold green]PASS[/bold green]"
            if c.status == "WARN":
                badge = "[bold yellow]WARN[/bold yellow]"
            elif c.status == "FAIL":
                badge = "[bold red]FAIL[/bold red]"

            msg = c.message
            if c.remedy:
                msg += f"\n[dim]Fix: {c.remedy}[/dim]"
            table.add_row(c.category, c.name, badge, msg)

        self.console.print(table)
        self.console.print()

    def render_config(self, diagnostics: dict[str, Any]) -> None:
        """Display safe configuration table with secrets scrubbed."""
        table = Table(
            title="GraphOS Runtime Configuration",
            border_style="dim",
            header_style="bold dim",
            expand=False,
        )
        table.add_column("Configuration Key", style="bold white")
        table.add_column("Configured Value", style="cyan")

        for k, v in sorted(diagnostics.items()):
            table.add_row(k, str(v))

        self.console.print(table)
        self.console.print()

    def render_tools(self, tools: list[ToolDefinition]) -> None:
        """Display discovered read-only MCP tools catalog."""
        table = Table(
            title=f"Discovered Read-Only MCP Tools ({len(tools)} Permitted)",
            border_style="dim",
            header_style="bold cyan",
            expand=False,
        )
        table.add_column("Tool Name", style="bold white")
        table.add_column("Description", style="white")
        table.add_column("Parameters", style="dim")

        for t in tools:
            params = t.parameters.get("properties", {}) if isinstance(t.parameters, dict) else {}
            param_str = ", ".join(params.keys()) if params else "none"
            desc = (t.description or "").strip().split("\n")[0][:70]
            table.add_row(t.name, desc, param_str)

        self.console.print(table)
        self.console.print()

    def render_history(self, turns: list[Any]) -> None:
        """Display session turn history table."""
        if not turns:
            self.console.print("[dim]No previous turns in this session.[/dim]\n")
            return

        table = Table(
            title=f"Session Turn History ({len(turns)} turns)",
            border_style="dim",
            header_style="bold dim",
            expand=False,
        )
        table.add_column("#", justify="center", style="dim")
        table.add_column("User Query", style="bold white")
        table.add_column("Calls", justify="center", style="cyan")
        table.add_column("Time", justify="center", style="dim")
        table.add_column("Key Verdict", style="white")

        for t in turns:
            verdict_line = (t.final_answer or "").strip().split("\n")[0][:60]
            table.add_row(
                str(t.turn_id),
                t.query[:50] + ("..." if len(t.query) > 50 else ""),
                str(t.tool_calls_count),
                f"{t.duration_seconds:.1f}s",
                verdict_line or "-",
            )

        self.console.print(table)
        self.console.print()
