from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from agent.models import AgentResult, ChatMessage, utc_now_iso

logger = logging.getLogger("graphos.agent.session")

SECRET_KEY_PATTERNS = re.compile(
    r"(key|token|password|secret|auth|credential|authorization)", re.IGNORECASE
)
SECRET_VALUE_PATTERNS = [
    re.compile(r"nvapi-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
]


def sanitize_secrets_in_obj(obj: Any) -> Any:
    """Recursively redact secrets and credentials from data structures before persistence."""
    if isinstance(obj, dict):
        sanitized = {}
        for k, v in obj.items():
            if SECRET_KEY_PATTERNS.search(str(k)):
                sanitized[k] = "********"
            else:
                sanitized[k] = sanitize_secrets_in_obj(v)
        return sanitized
    elif isinstance(obj, list):
        return [sanitize_secrets_in_obj(item) for item in obj]
    elif isinstance(obj, str):
        val = obj
        for pat in SECRET_VALUE_PATTERNS:
            val = pat.sub("********", val)
        return val
    return obj


@dataclass
class SessionTurn:
    """Record of a single conversational interaction within a session."""
    turn_id: int
    query: str
    final_answer: str
    evidence_summary: dict[str, Any]
    iterations: int
    tool_calls_count: int
    duration_seconds: float
    timestamp: str = field(default_factory=utc_now_iso)
    unresolved_questions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SessionState:
    """Complete persisted state of a GraphOS investigation session."""
    session_id: str
    created_at: str
    updated_at: str
    provider: str
    model: str
    turns: list[SessionTurn] = field(default_factory=list)
    verified_entities: dict[str, dict[str, Any]] = field(default_factory=dict)
    unresolved_gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "provider": self.provider,
            "model": self.model,
            "turns": [t.to_dict() for t in self.turns],
            "verified_entities": self.verified_entities,
            "unresolved_gaps": self.unresolved_gaps,
        }


class SessionManager:
    """
    Manages interactive multi-turn conversation context, local file persistence,
    and history tracking for GraphOS investigations.
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        storage_dir: Optional[Path] = None,
        provider: str = "nvidia",
        model: str = "openai/gpt-oss-20b",
    ) -> None:
        self.storage_dir = self._resolve_storage_dir(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.session_id = session_id or str(uuid.uuid4())[:8]
        now = utc_now_iso()
        self.state = SessionState(
            session_id=self.session_id,
            created_at=now,
            updated_at=now,
            provider=provider,
            model=model,
        )

        if session_id:
            self.load(session_id)

    @staticmethod
    def _resolve_storage_dir(custom_path: Optional[Path]) -> Path:
        if custom_path:
            return custom_path
        env_dir = os.getenv("GRAPHOS_SESSION_DIR")
        if env_dir:
            return Path(env_dir).expanduser().resolve()
        try:
            home_dir = Path.home() / ".graphos" / "sessions"
            home_dir.mkdir(parents=True, exist_ok=True)
            return home_dir
        except Exception:
            local_dir = Path("./.graphos/sessions").resolve()
            local_dir.mkdir(parents=True, exist_ok=True)
            return local_dir

    def new_session(self, provider: Optional[str] = None, model: Optional[str] = None) -> str:
        """Start a brand new investigation session."""
        self.session_id = str(uuid.uuid4())[:8]
        now = utc_now_iso()
        self.state = SessionState(
            session_id=self.session_id,
            created_at=now,
            updated_at=now,
            provider=provider or self.state.provider,
            model=model or self.state.model,
        )
        self.save()
        logger.info(f"Started new GraphOS session: {self.session_id}")
        return self.session_id

    def add_turn(self, query: str, result: AgentResult) -> SessionTurn:
        """Record an executed investigation turn and aggregate verified knowledge."""
        turn_id = len(self.state.turns) + 1
        turn = SessionTurn(
            turn_id=turn_id,
            query=query,
            final_answer=result.final_answer,
            evidence_summary=result.evidence_summary,
            iterations=result.total_iterations,
            tool_calls_count=result.total_tool_calls,
            duration_seconds=result.duration_seconds,
            timestamp=utc_now_iso(),
            unresolved_questions=result.unresolved_questions,
        )
        self.state.turns.append(turn)
        self.state.updated_at = utc_now_iso()

        entities_map = result.evidence_summary.get("entities") or {}
        for eid, edata in entities_map.items():
            if eid not in self.state.verified_entities:
                self.state.verified_entities[eid] = edata

        for q in result.unresolved_questions:
            if q not in self.state.unresolved_gaps:
                self.state.unresolved_gaps.append(q)

        self.save()
        return turn

    def get_conversation_context(self, max_turns: int = 3) -> list[ChatMessage]:
        """
        Produce a bounded conversation history for follow-up questions.
        Compresses previous turns into concise factual context without raw tool dumps.
        """
        if not self.state.turns:
            return []

        context_messages: list[ChatMessage] = []
        recent_turns = self.state.turns[-max_turns:]

        for t in recent_turns:
            context_messages.append(ChatMessage(role="user", content=t.query))
            summary = t.final_answer.strip()
            if len(summary) > 2000:
                summary = summary[:1900] + "\n\n[...Summary of prior findings condensed for context...]"
            context_messages.append(ChatMessage(role="assistant", content=summary))

        return context_messages

    def save(self) -> Path:
        """Persist session state to JSON on disk with secrets sanitized."""
        session_file = self.storage_dir / f"{self.session_id}.json"
        raw_dict = self.state.to_dict()
        safe_dict = sanitize_secrets_in_obj(raw_dict)
        try:
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(safe_dict, f, indent=2)
            logger.debug(f"Saved session {self.session_id} to {session_file}")
        except Exception as exc:
            logger.warning(f"Failed to persist session to {session_file}: {exc}")
        return session_file

    def load(self, session_id: str) -> bool:
        """Load session state from disk."""
        session_file = self.storage_dir / f"{session_id}.json"
        if not session_file.exists():
            return False

        try:
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            turns: list[SessionTurn] = []
            for t_data in data.get("turns", []):
                turns.append(
                    SessionTurn(
                        turn_id=t_data["turn_id"],
                        query=t_data["query"],
                        final_answer=t_data["final_answer"],
                        evidence_summary=t_data.get("evidence_summary", {}),
                        iterations=t_data.get("iterations", 1),
                        tool_calls_count=t_data.get("tool_calls_count", 0),
                        duration_seconds=t_data.get("duration_seconds", 0.0),
                        timestamp=t_data.get("timestamp", utc_now_iso()),
                        unresolved_questions=t_data.get("unresolved_questions", []),
                    )
                )

            self.session_id = data["session_id"]
            self.state = SessionState(
                session_id=data["session_id"],
                created_at=data.get("created_at", utc_now_iso()),
                updated_at=data.get("updated_at", utc_now_iso()),
                provider=data.get("provider", "nvidia"),
                model=data.get("model", "openai/gpt-oss-20b"),
                turns=turns,
                verified_entities=data.get("verified_entities", {}),
                unresolved_gaps=data.get("unresolved_gaps", []),
            )
            return True
        except Exception as exc:
            logger.error(f"Error loading session {session_id}: {exc}")
            return False

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all saved sessions in the storage directory."""
        results: list[dict[str, Any]] = []
        if not self.storage_dir.exists():
            return results

        for p in sorted(self.storage_dir.glob("*.json"), key=os.path.getmtime, reverse=True):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    results.append({
                        "session_id": data.get("session_id", p.stem),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                        "turns_count": len(data.get("turns", [])),
                        "provider": data.get("provider", "unknown"),
                        "model": data.get("model", "unknown"),
                    })
            except Exception:
                continue
        return results

    def clear(self) -> None:
        """Clear the current session's conversation turns."""
        self.state.turns.clear()
        self.state.verified_entities.clear()
        self.state.unresolved_gaps.clear()
        self.state.updated_at = utc_now_iso()
        self.save()
