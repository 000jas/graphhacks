from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import find_dotenv, load_dotenv

root_env = Path(__file__).resolve().parent.parent / ".env"
current_env = Path(__file__).resolve().parent / ".env"
if root_env.exists():
    load_dotenv(dotenv_path=root_env)
elif current_env.exists():
    load_dotenv(dotenv_path=current_env)
else:
    load_dotenv(find_dotenv())

SAFE_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
SAFE_RELATIONSHIP_PATTERN = re.compile(r"^[a-zA-Z0-9_]{1,64}$")
SAFE_PROPERTY_PATTERN = re.compile(r"^[a-zA-Z0-9_]{1,64}$")


def validate_identifier(name: str, field_name: str = "identifier") -> str:
    """Validate a general safe identifier (ID, graph name, kind)."""
    target = (name or "").strip()
    if not SAFE_IDENTIFIER_PATTERN.fullmatch(target):
        raise ValueError(
            f"Invalid {field_name} '{target}'. Must match [a-zA-Z0-9_-]{{1,64}}"
        )
    return target


def validate_relationship_type(rel_type: str) -> str:
    """Validate relationship type matches safe alphanumeric/underscore pattern."""
    target = (rel_type or "").strip()
    if not SAFE_RELATIONSHIP_PATTERN.fullmatch(target):
        raise ValueError(
            f"Invalid relationship type '{target}'. Must match [a-zA-Z0-9_]{{1,64}}"
        )
    return target


def validate_property_name(prop_name: str) -> str:
    """Validate property name matches safe alphanumeric/underscore pattern."""
    target = (prop_name or "").strip()
    if not SAFE_PROPERTY_PATTERN.fullmatch(target):
        raise ValueError(
            f"Invalid property name '{target}'. Must match [a-zA-Z0-9_]{{1,64}}"
        )
    return target


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    host: str = os.getenv(
        "FALKORDB_HOST",
        "r-6jissuruar.instance-27k50cn68.hc-7up0crkyn.ap-south-1.aws.f2e0a955bb84.cloud",
    )
    port: int = int(os.getenv("FALKORDB_PORT", "54637"))
    username: Optional[str] = os.getenv("FALKORDB_USERNAME", "falkordb") or None
    password: Optional[str] = os.getenv("FALKORDB_PASSWORD", "aOuxFFj8vO6A") or None
    ssl: bool = os.getenv("FALKORDB_SSL", "false").lower() in ("true", "1", "yes")

    default_graph: str = os.getenv("GRAPHOS_GRAPH_NAME", "ALL_GRAPHS")
    default_tenant: str = os.getenv("GRAPHOS_DEFAULT_TENANT", "default")
    max_traversal_depth: int = int(os.getenv("GRAPHOS_MAX_DEPTH", "6"))
    max_path_limit: int = int(os.getenv("GRAPHOS_MAX_PATH_LIMIT", "50"))
    query_timeout_ms: int = int(os.getenv("GRAPHOS_QUERY_TIMEOUT_MS", "15000"))
    max_batch_entities: int = int(os.getenv("GRAPHOS_MAX_BATCH_ENTITIES", "50"))

    def validate_graph_name(self, name: Optional[str] = None) -> str:
        """Validate and return safe graph/tenant identifier."""
        target = (name or self.default_graph or "ALL_GRAPHS").strip()
        return validate_identifier(target, field_name="graph name")

    def masked_connection_info(self) -> dict[str, object]:
        """Return connection metadata without exposing secrets."""
        return {
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "ssl_configured": self.ssl,
            "has_password": bool(self.password),
            "default_graph": self.default_graph,
            "default_tenant": self.default_tenant,
        }


settings = Settings()
