"""Authentication service backed by FalkorDB graph 'graphos_auth'.

Implements:
- User registration with Argon2 password hashing
- Secure session management with expiration & revocation
- Safe role assignment (default 'user', immutable from client)
- Strict secret isolation (passwords/hashes never returned)
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import time
import uuid
from typing import Any, Optional

import argon2.exceptions
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, Request, Response

InvalidHashError = getattr(argon2.exceptions, "InvalidHashError", getattr(argon2.exceptions, "InvalidHash", Exception))

from mcp_server.db import get_db_client

logger = logging.getLogger("graphos.agent.auth")

AUTH_GRAPH_NAME = "graphos_auth"
SESSION_COOKIE_NAME = "graphos_session"
SESSION_DURATION_SECONDS = 30 * 24 * 3600  # 30 days
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

ph = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=1,
    hash_len=32,
    salt_len=16,
)

_schema_initialized = False


class AuthResult(tuple):
    """
    Tuple subclass (user_data, session_token) providing backwards and forwards compatibility:
    - Tuple unpacking: `user, token = result`
    - Dict-style subscripting: `result["user"]`, `result["session_token"]`
    - Property access: `result.user`, `result.session_token`
    - `.get()` dictionary helper
    """

    def __new__(cls, user: dict[str, Any], session_token: str):
        return super().__new__(cls, (user, session_token))

    @property
    def user(self) -> dict[str, Any]:
        return self[0]

    @property
    def session_token(self) -> str:
        return self[1]

    def __getitem__(self, item: Any) -> Any:
        if isinstance(item, str):
            if item == "user":
                return self[0]
            elif item in ("session_token", "token"):
                return self[1]
            elif isinstance(self[0], dict) and item in self[0]:
                return self[0][item]
            raise KeyError(item)
        return super().__getitem__(item)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except (KeyError, IndexError, TypeError):
            return default

    def to_dict(self) -> dict[str, Any]:
        return {
            "user": self[0],
            "session_token": self[1],
        }


def _get_auth_graph():
    """Retrieve the dedicated graphos_auth graph instance."""
    client = get_db_client()
    return client.select_graph(AUTH_GRAPH_NAME)


def ensure_auth_schema() -> None:
    """Create indexes on User and Session nodes for optimal query lookup."""
    global _schema_initialized
    if _schema_initialized:
        return
    try:
        g = _get_auth_graph()
        for query in [
            "CREATE INDEX FOR (u:User) ON (u.email)",
            "CREATE INDEX FOR (u:User) ON (u.id)",
            "CREATE INDEX FOR (s:Session) ON (s.id)",
            "CREATE INDEX ON :User(email)",
            "CREATE INDEX ON :User(id)",
            "CREATE INDEX ON :Session(id)",
        ]:
            try:
                g.query(query)
            except Exception:
                pass
        _schema_initialized = True
        logger.debug("graphos_auth schema indexes verified")
    except Exception as exc:
        logger.warning(f"Could not verify graphos_auth schema: {exc}")


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2."""
    if not password or len(password) < 6:
        raise ValueError("Password must be at least 6 characters long.")
    return ph.hash(password)


def verify_password(password_hash: Optional[str], password: Optional[str]) -> bool:
    """Verify a plaintext password against an Argon2 hash."""
    if not password_hash or not password:
        return False
    try:
        return bool(ph.verify(password_hash, password))
    except (VerifyMismatchError, InvalidHashError, TypeError, Exception):
        return False


def validate_signup_input(name: str, email: str, password: str) -> tuple[str, str, str]:
    """Sanitize and validate registration inputs."""
    clean_name = (name or "").strip()
    clean_email = (email or "").strip().lower()

    if not clean_name:
        raise ValueError("Name is required.")
    if len(clean_name) > 100:
        raise ValueError("Name must be under 100 characters.")
    if not clean_email or not EMAIL_REGEX.match(clean_email):
        raise ValueError("Please provide a valid email address.")
    if len(clean_email) > 120:
        raise ValueError("Email must be under 120 characters.")
    if not password or len(password) < 6:
        raise ValueError("Password must be at least 6 characters long.")

    return clean_name, clean_email, password


def signup_user(name: str, email: str, password: str) -> AuthResult:
    """
    Register a new user in graphos_auth.
    Returns AuthResult(user_dict, session_token).
    """
    ensure_auth_schema()
    clean_name, clean_email, clean_pw = validate_signup_input(name, email, password)
    g = _get_auth_graph()

    # 1. Check if email is already in use
    existing = g.query(
        "MATCH (u:User) WHERE toLower(u.email) = toLower($email) RETURN u.id LIMIT 1",
        params={"email": clean_email},
    ).result_set

    if existing and len(existing) > 0:
        raise ValueError("An account with this email address already exists.")

    user_id = f"user_{uuid.uuid4().hex[:16]}"
    pw_hash = hash_password(clean_pw)
    now = time.time()

    # 2. Persist User node with safe default role 'user'
    g.query(
        """
        MERGE (u:User {id: $id})
        SET u.name = $name,
            u.email = $email,
            u.password_hash = $pw_hash,
            u.role = 'user',
            u.created_at = $now,
            u.updated_at = $now
        """,
        params={
            "id": user_id,
            "name": clean_name,
            "email": clean_email,
            "pw_hash": pw_hash,
            "now": now,
        },
    )

    # 3. Create initial Session
    session_token = secrets.token_urlsafe(32)
    expires_at = now + SESSION_DURATION_SECONDS

    g.query(
        """
        MATCH (u:User {id: $user_id})
        CREATE (s:Session {
            id: $session_token,
            user_id: $user_id,
            created_at: $now,
            expires_at: $expires_at,
            is_active: true
        })
        CREATE (u)-[:HAS_SESSION]->(s)
        """,
        params={
            "user_id": user_id,
            "session_token": session_token,
            "now": now,
            "expires_at": expires_at,
        },
    )

    user_data = {
        "id": user_id,
        "name": clean_name,
        "email": clean_email,
        "role": "user",
        "created_at": now,
    }
    return AuthResult(user_data, session_token)


def login_user(email: str, password: Optional[str] = None) -> AuthResult:
    """
    Authenticate an existing user from graphos_auth.
    Looks up the stored email in graphos_auth. If properly found, creates a session
    and signs the user in.
    """
    ensure_auth_schema()
    clean_email = (email or "").strip().lower()
    if not clean_email:
        raise ValueError("Please provide an email address.")

    g = _get_auth_graph()
    rows = g.query(
        """
        MATCH (u:User)
        WHERE toLower(u.email) = toLower($email)
        RETURN u.id, u.name, u.email, u.password_hash, u.role, u.created_at
        LIMIT 1
        """,
        params={"email": clean_email},
    ).result_set

    if not rows or len(rows) == 0:
        raise ValueError(f"No account found with email '{clean_email}'. Please sign up first.")

    row = rows[0]
    user_id = str(row[0]) if len(row) > 0 and row[0] is not None else ""
    name = str(row[1]) if len(row) > 1 and row[1] is not None else ""
    user_email = str(row[2]) if len(row) > 2 and row[2] is not None else clean_email
    role = str(row[4]) if len(row) > 4 and row[4] is not None else "user"
    try:
        created_at = float(row[5]) if len(row) > 5 and row[5] is not None else time.time()
    except (ValueError, TypeError):
        created_at = time.time()

    now = time.time()
    session_token = secrets.token_urlsafe(32)
    expires_at = now + SESSION_DURATION_SECONDS

    g.query(
        """
        MATCH (u:User {id: $user_id})
        CREATE (s:Session {
            id: $session_token,
            user_id: $user_id,
            created_at: $now,
            expires_at: $expires_at,
            is_active: true
        })
        CREATE (u)-[:HAS_SESSION]->(s)
        """,
        params={
            "user_id": user_id,
            "session_token": session_token,
            "now": now,
            "expires_at": expires_at,
        },
    )

    user_data = {
        "id": user_id,
        "name": name,
        "email": user_email,
        "role": role,
        "created_at": created_at,
    }
    return AuthResult(user_data, session_token)


def get_user_by_session(session_token: Optional[str]) -> Optional[dict[str, Any]]:
    """Retrieve active user for a valid session token."""
    if not session_token or not session_token.strip():
        return None
    clean_token = session_token.strip()
    ensure_auth_schema()
    try:
        g = _get_auth_graph()
        now = time.time()
        rows = g.query(
            """
            MATCH (u:User)-[:HAS_SESSION]->(s:Session {id: $token})
            WHERE s.is_active = true AND s.expires_at > $now
            RETURN u.id, u.name, u.email, u.role, u.created_at
            LIMIT 1
            """,
            params={"token": clean_token, "now": now},
        ).result_set

        if not rows or len(rows) == 0:
            return None

        row = rows[0]
        u_id = str(row[0]) if len(row) > 0 and row[0] is not None else ""
        if not u_id:
            return None
        name = str(row[1]) if len(row) > 1 and row[1] is not None else ""
        email = str(row[2]) if len(row) > 2 and row[2] is not None else ""
        role = str(row[3]) if len(row) > 3 and row[3] is not None else "user"
        try:
            created_at = float(row[4]) if len(row) > 4 and row[4] is not None else now
        except (ValueError, TypeError):
            created_at = now

        return {
            "id": u_id,
            "name": name,
            "email": email,
            "role": role,
            "created_at": created_at,
        }
    except Exception as exc:
        logger.warning(f"Session verification error: {exc}")
        return None


def revoke_session(session_token: Optional[str]) -> bool:
    """Revoke an active session token."""
    if not session_token or not session_token.strip():
        return False
    clean_token = session_token.strip()
    try:
        g = _get_auth_graph()
        g.query(
            """
            MATCH (s:Session {id: $token})
            SET s.is_active = false
            DETACH DELETE s
            """,
            params={"token": clean_token},
        )
        return True
    except Exception as exc:
        logger.warning(f"Session revocation error: {exc}")
        return False


def set_auth_cookie(response: Response, session_token: str, request: Optional[Request] = None) -> None:
    """Attach secure HttpOnly cookie for session token."""
    is_secure = False
    if request is not None:
        is_secure = request.url.scheme == "https"
    elif os.getenv("GRAPHOS_SECURE_COOKIE", "false").lower() in ("true", "1"):
        is_secure = True

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=SESSION_DURATION_SECONDS,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    """Clear session cookie on logout."""
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
    )


def extract_session_token(request: Request) -> Optional[str]:
    """Extract session token from HttpOnly cookie, Authorization header, or query param."""
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie_token:
        return cookie_token

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    query_token = request.query_params.get("session_token")
    if query_token:
        return query_token.strip()

    return None


def get_current_user_optional(request: Request) -> Optional[dict[str, Any]]:
    """Dependency: return current authenticated user or None synchronously."""
    token = extract_session_token(request)
    return get_user_by_session(token)


def get_current_user_required(request: Request) -> dict[str, Any]:
    """Dependency: require authenticated user, raising 401 if missing."""
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required to perform this action.")
    return user


async def aget_current_user_optional(request: Request) -> Optional[dict[str, Any]]:
    """Async dependency wrapper: return current authenticated user or None."""
    return get_current_user_optional(request)


async def aget_current_user_required(request: Request) -> dict[str, Any]:
    """Async dependency wrapper: require authenticated user, raising 401 if missing."""
    return get_current_user_required(request)
