from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from agent.cli import async_main, build_parser, execute_oneshot_investigation
from agent.config import AgentSettings
from agent.doctor import GraphOSDoctor
from agent.engine import GraphOSInvestigator
from agent.models import AgentResult, AgentStep
from agent.providers.mock_provider import MockProvider
from agent.repl import InteractiveREPL
from agent.session import SessionManager
from agent.ui import TerminalUI


def test_cli_parser_structure() -> None:
    parser = build_parser()

    args = parser.parse_args(["--provider", "mock", "--json", "-q", "test query"])
    assert args.provider == "mock"
    assert args.json is True
    assert args.query == "test query"

    args_ask = parser.parse_args(["ask", "Why is payments delayed?", "--quiet"])
    assert args_ask.subcommand == "ask"
    assert args_ask.query == "Why is payments delayed?"
    assert args_ask.quiet is True

    assert parser.parse_args(["status"]).subcommand == "status"
    assert parser.parse_args(["doctor"]).subcommand == "doctor"
    assert parser.parse_args(["config"]).subcommand == "config"
    assert parser.parse_args(["tools"]).subcommand == "tools"
    assert parser.parse_args(["repl"]).subcommand == "repl"


def test_cli_status_subcommand(capsys) -> None:
    async def _run() -> None:
        parser = build_parser()
        args = parser.parse_args(["status", "--json"])
        code = await async_main(args)
        assert code == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "application_status" in data
        assert "provider" in data
        assert "allowed_tools" in data
        assert data["allowed_tools"] > 0
        assert data["execution_mode"] == "Read-Only (Strict Guardrails)"

    asyncio.run(_run())


def test_cli_doctor_subcommand(capsys) -> None:
    async def _run() -> None:
        parser = build_parser()
        args = parser.parse_args(["doctor", "--json"])
        code = await async_main(args)
        assert code == 0

        captured = capsys.readouterr()
        checks = json.loads(captured.out)
        assert isinstance(checks, list)
        check_names = [c["name"] for c in checks]
        assert "Python Runtime" in check_names
        assert "Required Packages" in check_names
        assert "Read-Only Safety" in check_names

    asyncio.run(_run())


def test_cli_config_subcommand(capsys) -> None:
    async def _run() -> None:
        parser = build_parser()
        args = parser.parse_args(["config", "--json"])
        code = await async_main(args)
        assert code == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["read_only_enforced"] is True
        assert "credential_masked" in data
        assert "nvapi-" not in captured.out
        assert "aOux" not in captured.out

    asyncio.run(_run())


def test_cli_tools_subcommand(capsys) -> None:
    async def _run() -> None:
        parser = build_parser()
        args = parser.parse_args(["tools", "--json"])
        code = await async_main(args)
        assert code == 0

        captured = capsys.readouterr()
        tools_list = json.loads(captured.out)
        assert isinstance(tools_list, list)
        tool_names = [t["name"] for t in tools_list]
        assert "search_connected_entities" in tool_names
        assert "get_entity_profile" in tool_names
        assert "traverse_relationships" in tool_names
        assert "execute_approved_action" not in tool_names
        assert "propose_action" not in tool_names

    asyncio.run(_run())


def test_cli_oneshot_investigation_json(capsys) -> None:
    async def _run() -> None:
        parser = build_parser()
        args = parser.parse_args([
            "ask",
            "Why is the payments release delayed?",
            "--provider", "mock",
            "--json",
        ])
        code = await async_main(args)
        assert code == 0

        captured = capsys.readouterr()
        result_data = json.loads(captured.out)
        assert result_data["success"] is True
        assert result_data["total_iterations"] >= 2
        assert result_data["total_tool_calls"] >= 2
        assert "payments" in result_data["final_answer"].lower()
        assert "pr-482" in result_data["final_answer"].lower() or "pr #482" in result_data["final_answer"].lower()
        assert result_data["provider_info"]["provider"] == "mock"

    asyncio.run(_run())


def test_repl_slash_commands() -> None:
    async def _run() -> None:
        settings = AgentSettings(llm_provider="mock", read_only=True)
        ui = TerminalUI(no_color=True, quiet=True)
        repl = InteractiveREPL(settings=settings, ui=ui)

        exit_flag = await repl._handle_slash_command("/help")
        assert exit_flag is False

        exit_flag = await repl._handle_slash_command("/status")
        assert exit_flag is False

        exit_flag = await repl._handle_slash_command("/doctor")
        assert exit_flag is False

        exit_flag = await repl._handle_slash_command("/config")
        assert exit_flag is False

        exit_flag = await repl._handle_slash_command("/model mock test-mock-model")
        assert exit_flag is False
        assert repl.settings.llm_provider == "mock"
        assert repl.settings.llm_model == "test-mock-model"

        exit_flag = await repl._handle_slash_command("/new")
        assert exit_flag is False
        assert len(repl.session_manager.state.turns) == 0

        exit_flag = await repl._handle_slash_command("/history")
        assert exit_flag is False

        exit_flag = await repl._handle_slash_command("/exit")
        assert exit_flag is True

    asyncio.run(_run())


def test_repl_multiturn_followup_investigation() -> None:
    """Verify stateful multi-turn follow-up with prior context retention."""
    async def _run() -> None:
        settings = AgentSettings(llm_provider="mock", read_only=True)
        ui = TerminalUI(no_color=True, quiet=True)
        repl = InteractiveREPL(settings=settings, ui=ui)

        await repl._execute_investigation_turn("Why is the payments release delayed?")
        assert len(repl.session_manager.state.turns) == 1
        turn1 = repl.session_manager.state.turns[0]
        assert "pr-482" in turn1.final_answer.lower() or "pr #482" in turn1.final_answer.lower()

        await repl._execute_investigation_turn("Who can replace Liam Patel for the code review?")
        assert len(repl.session_manager.state.turns) == 2
        turn2 = repl.session_manager.state.turns[1]
        assert "ravi kulkarni" in turn2.final_answer.lower()
        assert "policy" in turn2.final_answer.lower()

        ctx = repl.session_manager.get_conversation_context(max_turns=3)
        assert len(ctx) == 4
        assert "Why is the payments release delayed?" in ctx[0].content
        assert "replace Liam Patel" in ctx[2].content

    asyncio.run(_run())
