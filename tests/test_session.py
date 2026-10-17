from __future__ import annotations

import json
from pathlib import Path
import pytest

from agent.models import AgentResult, AgentStep, ToolCall
from agent.session import SessionManager, sanitize_secrets_in_obj


def test_sanitize_secrets_in_obj() -> None:
    raw = {
        "api_key": "nvapi-abcdefghijklmnopqrstuvwxyz123456",
        "nested": {
            "password": "super_secret_password",
            "safe_field": "safe_value",
            "openai_token": "sk-proj-1234567890abcdefghijklmn",
        },
        "items": [
            {"token": "ghp_123456789012345678901234567890"},
            {"name": "payments_release"},
        ],
    }

    sanitized = sanitize_secrets_in_obj(raw)

    assert sanitized["api_key"] == "********"
    assert sanitized["nested"]["password"] == "********"
    assert sanitized["nested"]["openai_token"] == "********"
    assert sanitized["nested"]["safe_field"] == "safe_value"
    assert sanitized["items"][0]["token"] == "********"
    assert sanitized["items"][1]["name"] == "payments_release"


def test_session_manager_turn_lifecycle(tmp_path: Path) -> None:
    sm = SessionManager(storage_dir=tmp_path, provider="mock", model="mock-model")
    assert sm.session_id is not None
    assert len(sm.state.turns) == 0

    result1 = AgentResult(
        objective="Why is payments delayed?",
        success=True,
        final_answer="Payments is delayed by PR #482 awaiting review.",
        evidence_summary={
            "total_entities_verified": 2,
            "entities": {
                "release-payments-2026-10": {"name": "Payments Release", "kind": "Release"},
                "pr-482": {"name": "PR #482", "kind": "PullRequest"},
            },
        },
        steps=[AgentStep(iteration=1, thought="Thinking")],
        total_iterations=1,
        total_tool_calls=1,
        duration_seconds=0.5,
    )

    turn1 = sm.add_turn("Why is payments delayed?", result1)
    assert turn1.turn_id == 1
    assert len(sm.state.turns) == 1
    assert "release-payments-2026-10" in sm.state.verified_entities
    assert "pr-482" in sm.state.verified_entities

    ctx = sm.get_conversation_context(max_turns=3)
    assert len(ctx) == 2
    assert ctx[0].role == "user"
    assert "Why is payments delayed?" in ctx[0].content
    assert ctx[1].role == "assistant"
    assert "PR #482" in ctx[1].content

    saved_file = sm.save()
    assert saved_file.exists()

    sm2 = SessionManager(session_id=sm.session_id, storage_dir=tmp_path)
    assert len(sm2.state.turns) == 1
    assert sm2.state.turns[0].query == "Why is payments delayed?"
    assert "pr-482" in sm2.state.verified_entities

    sessions_list = sm.list_sessions()
    assert len(sessions_list) >= 1
    assert any(s["session_id"] == sm.session_id for s in sessions_list)

    sm2.clear()
    assert len(sm2.state.turns) == 0
    assert len(sm2.state.verified_entities) == 0
