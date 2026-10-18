"""Chat history persistence service backed by FalkorDB graph 'graphos_history'.

Implements isolated graph storage for:
- (User)-[:HAS_CONVERSATION]->(Conversation)
- (Conversation)-[:HAS_MESSAGE]->(Message)

Guarantees tenant isolation: users can strictly only access and query conversations
they own.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Optional

from mcp_server.db import get_db_client

logger = logging.getLogger("graphos.agent.history")

HISTORY_GRAPH_NAME = "graphos_history"
_history_schema_initialized = False


def _get_history_graph():
    """Retrieve the dedicated graphos_history graph instance."""
    client = get_db_client()
    return client.select_graph(HISTORY_GRAPH_NAME)


def ensure_history_schema() -> None:
    """Create indexes on User, Conversation, and Message nodes."""
    global _history_schema_initialized
    if _history_schema_initialized:
        return
    try:
        g = _get_history_graph()
        for query in [
            "CREATE INDEX FOR (u:User) ON (u.id)",
            "CREATE INDEX FOR (c:Conversation) ON (c.id)",
            "CREATE INDEX FOR (m:Message) ON (m.id)",
            "CREATE INDEX ON :User(id)",
            "CREATE INDEX ON :Conversation(id)",
            "CREATE INDEX ON :Message(id)",
        ]:
            try:
                g.query(query)
            except Exception:
                pass
        _history_schema_initialized = True
        logger.debug("graphos_history schema indexes verified")
    except Exception as exc:
        logger.warning(f"Could not verify graphos_history schema: {exc}")


def _resolve_conv_and_user_args(
    first: Optional[str] = None,
    second: Optional[str] = None,
    *,
    conversation_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """
    Resolve (conversation_id, user_id) regardless of whether callers passed:
    - (conversation_id, user_id) positional
    - (user_id, conversation_id) positional (legacy signature)
    - (conversation_id) only positional
    - keyword arguments in any order
    """
    c_id = conversation_id
    u_id = user_id

    if first is not None:
        first_str = first.strip()
        second_str = second.strip() if second is not None else None

        if second_str is not None:
            # Check for legacy parameter swap: (user_id, conversation_id)
            if first_str.startswith("user_") and (second_str.startswith("conv_") or not u_id):
                u_id = first_str
                c_id = second_str
            elif first_str.startswith("conv_") and second_str.startswith("user_"):
                c_id = first_str
                u_id = second_str
            else:
                # Default order: conversation_id first, user_id second
                if c_id is None:
                    c_id = first_str
                if u_id is None:
                    u_id = second_str
        else:
            # Single positional argument -> conversation_id
            if c_id is None:
                c_id = first_str

    if not c_id:
        raise ValueError("conversation_id is required.")

    return c_id, u_id


def create_conversation(
    user_id: str,
    title: Optional[str] = None,
    graph_name: Optional[str] = None,
) -> dict[str, Any]:
    """Create a new conversation associated with the given user."""
    clean_uid = user_id.strip() if user_id else ""
    if not clean_uid:
        raise ValueError("user_id is required to create a conversation.")

    ensure_history_schema()
    g = _get_history_graph()
    conv_id = f"conv_{uuid.uuid4().hex[:16]}"
    clean_title = (title or "New Investigation").strip()
    clean_graph = (graph_name or "ALL_GRAPHS").strip()
    now = time.time()

    g.query(
        """
        MERGE (u:User {id: $user_id})
        CREATE (c:Conversation {
            id: $conv_id,
            title: $title,
            graph_name: $graph_name,
            created_at: $now,
            updated_at: $now,
            user_id: $user_id
        })
        CREATE (u)-[:HAS_CONVERSATION]->(c)
        """,
        params={
            "user_id": clean_uid,
            "conv_id": conv_id,
            "title": clean_title,
            "graph_name": clean_graph,
            "now": now,
        },
    )

    return {
        "id": conv_id,
        "title": clean_title,
        "graph_name": clean_graph,
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
    }


def list_conversations(user_id: str) -> list[dict[str, Any]]:
    """List all conversations owned by the user, ordered by most recently active."""
    clean_uid = user_id.strip() if user_id else ""
    if not clean_uid:
        return []

    ensure_history_schema()
    g = _get_history_graph()
    try:
        rows = g.query(
            """
            MATCH (u:User {id: $user_id})-[:HAS_CONVERSATION]->(c:Conversation)
            OPTIONAL MATCH (c)-[:HAS_MESSAGE]->(m:Message)
            RETURN c.id, c.title, c.graph_name, c.created_at, c.updated_at, count(m)
            ORDER BY c.updated_at DESC
            """,
            params={"user_id": clean_uid},
        ).result_set

        conversations: list[dict[str, Any]] = []
        for r in rows:
            if not isinstance(r, (list, tuple)) or len(r) == 0:
                continue
            conversations.append({
                "id": str(r[0]),
                "title": str(r[1] if len(r) > 1 and r[1] is not None else "Investigation"),
                "graph_name": str(r[2] if len(r) > 2 and r[2] is not None else "ALL_GRAPHS"),
                "created_at": float(r[3] if len(r) > 3 and r[3] is not None else 0),
                "updated_at": float(r[4] if len(r) > 4 and r[4] is not None else 0),
                "message_count": int(r[5] if len(r) > 5 and r[5] is not None else 0),
            })
        return conversations
    except Exception as exc:
        logger.warning(f"Error listing conversations for {clean_uid}: {exc}")
        return []


def get_conversation(
    first: Optional[str] = None,
    second: Optional[str] = None,
    *,
    conversation_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Retrieve conversation detail with all messages.
    Supports:
    - get_conversation(conversation_id, user_id=None)
    - get_conversation(user_id, conversation_id) [legacy]
    - get_conversation(conversation_id="conv_...", user_id="user_...")
    Strict tenant validation: returns None if user_id is provided and the conversation does not belong to user_id.
    """
    try:
        target_conv_id, target_user_id = _resolve_conv_and_user_args(
            first, second, conversation_id=conversation_id, user_id=user_id
        )
    except ValueError:
        return None

    ensure_history_schema()
    g = _get_history_graph()
    try:
        if target_user_id:
            conv_rows = g.query(
                """
                MATCH (u:User {id: $user_id})-[:HAS_CONVERSATION]->(c:Conversation {id: $conv_id})
                RETURN c.id, c.title, c.graph_name, c.created_at, c.updated_at
                LIMIT 1
                """,
                params={"user_id": target_user_id, "conv_id": target_conv_id},
            ).result_set
        else:
            conv_rows = g.query(
                """
                MATCH (c:Conversation {id: $conv_id})
                RETURN c.id, c.title, c.graph_name, c.created_at, c.updated_at
                LIMIT 1
                """,
                params={"conv_id": target_conv_id},
            ).result_set

        if not conv_rows or len(conv_rows) == 0:
            return None

        conv_row = conv_rows[0]
        conv_meta: dict[str, Any] = {
            "id": str(conv_row[0]),
            "title": str(conv_row[1] if len(conv_row) > 1 and conv_row[1] is not None else "Investigation"),
            "graph_name": str(conv_row[2] if len(conv_row) > 2 and conv_row[2] is not None else "ALL_GRAPHS"),
            "created_at": float(conv_row[3] if len(conv_row) > 3 and conv_row[3] is not None else 0),
            "updated_at": float(conv_row[4] if len(conv_row) > 4 and conv_row[4] is not None else 0),
        }

        # Retrieve messages in chronological order
        msg_rows = g.query(
            """
            MATCH (c:Conversation {id: $conv_id})-[:HAS_MESSAGE]->(m:Message)
            RETURN m.id, m.role, m.content, m.timestamp, m.metadata_json
            ORDER BY m.timestamp ASC
            """,
            params={"conv_id": target_conv_id},
        ).result_set

        messages: list[dict[str, Any]] = []
        for mr in msg_rows:
            if not isinstance(mr, (list, tuple)) or len(mr) == 0:
                continue

            meta: dict[str, Any] = {}
            raw_meta = mr[4] if len(mr) > 4 else None
            if raw_meta:
                if isinstance(raw_meta, dict):
                    meta = raw_meta
                elif isinstance(raw_meta, (str, bytes, bytearray)):
                    try:
                        meta = json.loads(raw_meta)
                    except Exception:
                        meta = {}

            try:
                ts = float(mr[3]) if len(mr) > 3 and mr[3] is not None else 0.0
            except (ValueError, TypeError):
                ts = 0.0

            messages.append({
                "id": str(mr[0]),
                "role": str(mr[1]) if len(mr) > 1 and mr[1] is not None else "assistant",
                "content": str(mr[2]) if len(mr) > 2 and mr[2] is not None else "",
                "timestamp": ts,
                "metadata": meta,
            })

        conv_meta["messages"] = messages
        conv_meta["message_count"] = len(messages)
        return conv_meta
    except Exception as exc:
        logger.warning(f"Error fetching conversation {target_conv_id}: {exc}")
        return None


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Add a message to an existing conversation and update conversation timestamp.
    Guarantees message is never dropped: creates Conversation node if not already present.
    """
    clean_conv_id = conversation_id.strip() if conversation_id else ""
    if not clean_conv_id:
        raise ValueError("conversation_id is required to add a message.")

    ensure_history_schema()
    g = _get_history_graph()
    msg_id = f"msg_{uuid.uuid4().hex[:16]}"
    now = time.time()

    clean_role = (role or "user").strip().lower()
    clean_content = content or ""
    clean_meta = metadata if isinstance(metadata, dict) else {}
    meta_json = json.dumps(clean_meta, default=str)

    # 1. Ensure conversation exists and link new message
    g.query(
        """
        MERGE (c:Conversation {id: $conv_id})
        ON CREATE SET c.title = 'New Investigation',
                      c.graph_name = 'ALL_GRAPHS',
                      c.created_at = $now,
                      c.updated_at = $now
        CREATE (m:Message {
            id: $msg_id,
            role: $role,
            content: $content,
            timestamp: $now,
            metadata_json: $meta_json
        })
        CREATE (c)-[:HAS_MESSAGE]->(m)
        SET c.updated_at = $now
        """,
        params={
            "conv_id": clean_conv_id,
            "msg_id": msg_id,
            "role": clean_role,
            "content": clean_content,
            "now": now,
            "meta_json": meta_json,
        },
    )

    # 2. Update conversation title snippet for initial user prompt
    if clean_role == "user" and clean_content.strip():
        title_snippet = clean_content.strip().replace("\n", " ")[:60]
        try:
            g.query(
                """
                MATCH (c:Conversation {id: $conv_id})
                WHERE c.title = 'New Investigation' OR c.title = 'Investigation' OR c.title IS NULL
                SET c.title = $snippet
                """,
                params={"conv_id": clean_conv_id, "snippet": title_snippet},
            )
        except Exception as exc:
            logger.debug(f"Title snippet update skipped: {exc}")

    return {
        "id": msg_id,
        "conversation_id": clean_conv_id,
        "role": clean_role,
        "content": clean_content,
        "timestamp": now,
        "metadata": clean_meta,
    }


def delete_conversation(
    first: Optional[str] = None,
    second: Optional[str] = None,
    *,
    conversation_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> bool:
    """
    Delete a conversation and all its messages.
    Supports:
    - delete_conversation(conversation_id, user_id=None)
    - delete_conversation(user_id, conversation_id) [legacy]
    - delete_conversation(conversation_id="conv_...", user_id="user_...")
    Verifies ownership if user_id is provided.
    """
    try:
        target_conv_id, target_user_id = _resolve_conv_and_user_args(
            first, second, conversation_id=conversation_id, user_id=user_id
        )
    except ValueError:
        return False

    ensure_history_schema()
    g = _get_history_graph()
    try:
        if target_user_id:
            res = g.query(
                """
                MATCH (u:User {id: $user_id})-[:HAS_CONVERSATION]->(c:Conversation {id: $conv_id})
                OPTIONAL MATCH (c)-[:HAS_MESSAGE]->(m:Message)
                DETACH DELETE c, m
                RETURN count(c)
                """,
                params={"user_id": target_user_id, "conv_id": target_conv_id},
            ).result_set
        else:
            res = g.query(
                """
                MATCH (c:Conversation {id: $conv_id})
                OPTIONAL MATCH (c)-[:HAS_MESSAGE]->(m:Message)
                DETACH DELETE c, m
                RETURN count(c)
                """,
                params={"conv_id": target_conv_id},
            ).result_set

        return bool(res and len(res) > 0 and res[0][0] > 0)
    except Exception as exc:
        logger.warning(f"Error deleting conversation {target_conv_id}: {exc}")
        return False


def get_conversation_messages(conversation_id: str) -> list[dict[str, Any]]:
    """Retrieve all messages for a given conversation ID."""
    conv = get_conversation(conversation_id=conversation_id)
    if not conv:
        return []
    return conv.get("messages", [])


def update_conversation_title(conversation_id: str, title: str) -> bool:
    """Explicitly rename a conversation title."""
    clean_conv_id = conversation_id.strip() if conversation_id else ""
    clean_title = title.strip() if title else ""
    if not clean_conv_id or not clean_title:
        return False
    try:
        g = _get_history_graph()
        g.query(
            "MATCH (c:Conversation {id: $conv_id}) SET c.title = $title, c.updated_at = $now",
            params={"conv_id": clean_conv_id, "title": clean_title, "now": time.time()},
        )
        return True
    except Exception as exc:
        logger.warning(f"Error updating title for {clean_conv_id}: {exc}")
        return False
