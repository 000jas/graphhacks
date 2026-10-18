"""Unit tests for agent.auth and agent.chat_history edge cases and robustness."""

import time
import pytest
from agent.auth import (
    AuthResult,
    hash_password,
    verify_password,
    validate_signup_input,
    signup_user,
    login_user,
    get_user_by_session,
    revoke_session,
    extract_session_token,
)
from agent.chat_history import (
    _resolve_conv_and_user_args,
    create_conversation,
    list_conversations,
    get_conversation,
    add_message,
    delete_conversation,
)
from fastapi import Request


def test_auth_result_compatibility():
    """Verify AuthResult works as both tuple and dict-like object."""
    user = {"id": "user_123", "name": "Alice", "email": "alice@example.com"}
    token = "session_token_xyz"
    res = AuthResult(user, token)

    # Tuple unpacking
    u, t = res
    assert u["id"] == "user_123"
    assert t == "session_token_xyz"

    # Index access
    assert res[0] == user
    assert res[1] == token

    # Dict-like access
    assert res["user"] == user
    assert res["session_token"] == token
    assert res["token"] == token
    assert res["id"] == "user_123"
    assert res.get("user") == user
    assert res.get("session_token") == token
    assert res.get("nonexistent", "default") == "default"

    # Property access
    assert res.user == user
    assert res.session_token == token
    assert res.to_dict() == {"user": user, "session_token": token}


def test_password_hash_and_verification():
    """Verify Argon2 hashing and defensive error handling."""
    pw = "SuperSecurePassword123!"
    h = hash_password(pw)
    assert h.startswith("$argon2id$")
    assert verify_password(h, pw) is True
    assert verify_password(h, "wrong_password") is False
    assert verify_password(None, pw) is False
    assert verify_password(h, None) is False
    assert verify_password("invalid_hash_string", pw) is False

    with pytest.raises(ValueError):
        hash_password("short")


def test_signup_input_validation():
    """Verify input validation rules."""
    name, email, pw = validate_signup_input(" Bob ", " Bob@Example.COM ", "ValidPass123")
    assert name == "Bob"
    assert email == "bob@example.com"
    assert pw == "ValidPass123"

    with pytest.raises(ValueError):
        validate_signup_input("", "bob@example.com", "ValidPass123")
    with pytest.raises(ValueError):
        validate_signup_input("Bob", "invalid-email", "ValidPass123")
    with pytest.raises(ValueError):
        validate_signup_input("Bob", "bob@example.com", "short")


def test_chat_history_arg_resolution():
    """Verify _resolve_conv_and_user_args handles all positional and keyword combinations."""
    # (conversation_id, user_id) standard
    c, u = _resolve_conv_and_user_args("conv_111", "user_222")
    assert c == "conv_111"
    assert u == "user_222"

    # (user_id, conversation_id) legacy positional swap
    c, u = _resolve_conv_and_user_args("user_222", "conv_111")
    assert c == "conv_111"
    assert u == "user_222"

    # Single positional (conversation_id only)
    c, u = _resolve_conv_and_user_args("conv_333")
    assert c == "conv_333"
    assert u is None

    # Keyword args
    c, u = _resolve_conv_and_user_args(conversation_id="conv_444", user_id="user_555")
    assert c == "conv_444"
    assert u == "user_555"

    with pytest.raises(ValueError):
        _resolve_conv_and_user_args()


def test_live_chat_history_messages_and_metadata():
    """Verify add_message and get_conversation handle complex metadata with FalkorDB."""
    test_uid = f"user_test_{int(time.time())}"
    conv = create_conversation(user_id=test_uid, title="Initial Title", graph_name="ALL_GRAPHS")
    conv_id = conv["id"]

    # Add user message with dictionary metadata
    msg1 = add_message(
        conversation_id=conv_id,
        role="user",
        content="What is the connection between Account A and Account B?",
        metadata={"custom_flag": True, "source": "test"},
    )
    assert msg1["role"] == "user"

    # Add assistant message with nested metadata
    msg2 = add_message(
        conversation_id=conv_id,
        role="assistant",
        content="Here is the verified path.",
        metadata={"steps": [{"step": 1, "thought": "analyzing"}], "confidence": 0.99},
    )
    assert msg2["role"] == "assistant"

    # Retrieve conversation with user_id check
    detail = get_conversation(conversation_id=conv_id, user_id=test_uid)
    assert detail is not None
    assert len(detail["messages"]) == 2
    assert detail["messages"][0]["metadata"]["custom_flag"] is True
    assert detail["messages"][1]["metadata"]["confidence"] == 0.99

    # Retrieve conversation with single positional arg (internal lookup)
    detail_pos = get_conversation(conv_id)
    assert detail_pos is not None
    assert detail_pos["id"] == conv_id

    # Retrieve conversation with legacy arg order: (user_id, conversation_id)
    detail_legacy = get_conversation(test_uid, conv_id)
    assert detail_legacy is not None
    assert detail_legacy["id"] == conv_id

    # Clean up
    deleted = delete_conversation(conv_id, test_uid)
    assert deleted is True

    # Cannot retrieve after deletion
    assert get_conversation(conv_id, test_uid) is None


def test_login_user_stored_email():
    """Verify that login_user successfully signs in with a stored email and rejects an un-stored email."""
    # Test un-stored email raises ValueError
    with pytest.raises(ValueError) as excinfo:
        login_user("unregistered_random_xyz@example.com")
    assert "No account found with email" in str(excinfo.value)

    # Empty email raises ValueError
    with pytest.raises(ValueError):
        login_user("")

    # Register a new user and test sign in with stored email
    test_email = f"stored_test_{int(time.time())}@example.com"
    signup_user("Test Stored User", test_email, "SuperSecret123!")

    # Sign in with only stored email
    login_result = login_user(test_email)
    assert login_result.user["email"] == test_email
    assert login_result.user["name"] == "Test Stored User"
    assert login_result.session_token is not None
    assert len(login_result.session_token) > 20

