import pytest
from fastapi.testclient import TestClient
from agent.api import app, DEMO_SCENARIOS


client = TestClient(app)


def test_api_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "provider" in data
    assert "graph_name" in data
    assert data["read_only"] is True


def test_api_demo_scenarios():
    for scenario in ["fraud", "security", "codebase"]:
        response = client.get(f"/api/demo/{scenario}")
        assert response.status_code == 200
        data = response.json()
        assert data["scenario_id"] == scenario
        assert "final_answer" in data
        assert "evidence_summary" in data
        assert data["evidence_summary"]["unique_entities_count"] > 0
        assert len(data["evidence_summary"]["key_paths"]) > 0


def test_api_demo_investigate():
    payload = {
        "objective": "Investigate suspicious transactions and find connected entities",
        "mode": "demo",
    }
    response = client.post("/api/investigate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "final_answer" in data
    assert "evidence_summary" in data
    assert "acc-mule-881" in data["evidence_summary"]["entities"]


def test_api_stream_investigate_demo():
    payload = {
        "objective": "Investigate suspicious transactions and find connected entities",
        "mode": "demo",
    }
    response = client.post("/api/investigate/stream", json=payload)
    assert response.status_code == 200
    text = response.text
    assert "data: " in text
    assert "complete" in text


def test_system_graphs_isolated_from_api_and_dropdown():
    """Verify system graphs (graphos_auth, graphos_history) never leak into dropdown and return 403 on direct access."""
    # 1. Dropdown dynamic discovery filter
    resp = client.get("/api/graphs")
    assert resp.status_code == 200
    graphs = resp.json().get("graphs", [])
    assert "graphos_auth" not in graphs
    assert "graphos_history" not in graphs
    assert "graphos_system" not in graphs
    assert "graphos_internal" not in graphs

    # 2. Direct API access guardrails
    assert client.get("/api/schema?tenant_graph=graphos_auth").status_code == 403
    assert client.get("/api/schema?tenant_graph=graphos_history").status_code == 403
    assert client.get("/api/graph/preview?tenant_graph=graphos_auth").status_code == 403
    assert client.get("/api/graph/preview?tenant_graph=graphos_history").status_code == 403
    assert client.post("/api/investigate", json={"objective": "probe", "tenant_graph": "graphos_auth"}).status_code == 403
    assert client.post("/api/investigate/stream", json={"objective": "probe", "tenant_graph": "graphos_auth"}).status_code == 403
    assert client.post("/api/ingest/code-json", json={"graph_name": "graphos_auth", "data": {}}).status_code == 403
    assert client.post("/api/ingest/csv", json={"graph_name": "graphos_history", "csv_text": "a,b\n1,2"}).status_code == 403
    assert client.post("/api/remediation/approve", json={"action_type": "BLOCK", "target_id": "x", "rationale": "r", "tenant_graph": "graphos_auth"}).status_code == 403


def test_auth_signup_login_logout_and_argon2():
    """Verify user signup with Argon2 hashing, role defaulting, session cookie, and logout."""
    import uuid
    email = f"analyst_{uuid.uuid4().hex[:8]}@falkordb.com"
    pwd = "EnterprisePassword99!"

    # Signup
    signup_res = client.post("/api/auth/signup", json={"name": "Alice Analyst", "email": email, "password": pwd})
    assert signup_res.status_code == 200
    signup_data = signup_res.json()
    assert signup_data["status"] == "success"
    user = signup_data["user"]
    assert user["email"] == email
    assert user["role"] == "user"  # Safe default role
    assert "password" not in user
    assert "password_hash" not in user
    token = signup_data["session_token"]
    assert token

    # Check session cookie authentication via /api/auth/me
    me_res = client.get("/api/auth/me", cookies={"graphos_session": token})
    assert me_res.status_code == 200
    assert me_res.json()["authenticated"] is True
    assert me_res.json()["user"]["email"] == email

    # Logout
    logout_res = client.post("/api/auth/logout", cookies={"graphos_session": token})
    assert logout_res.status_code == 200

    # Verify session revoked
    me_revoked = client.get("/api/auth/me", cookies={"graphos_session": token})
    assert me_revoked.status_code == 200
    assert me_revoked.json()["authenticated"] is False

    # Login back
    login_res = client.post("/api/auth/login", json={"email": email, "password": pwd})
    assert login_res.status_code == 200
    assert login_res.json()["user"]["email"] == email
    new_token = login_res.json()["session_token"]
    assert new_token != token

    # Invalid login fails when email is not stored in FalkorDB
    bad_res = client.post("/api/auth/login", json={"email": "nonexistent_analyst@falkordb.com"})
    assert bad_res.status_code == 401


def test_chat_history_persistence_and_isolation():
    """Verify persistent chat conversations and strict tenant isolation."""
    import uuid
    email_a = f"usera_{uuid.uuid4().hex[:8]}@example.com"
    email_b = f"userb_{uuid.uuid4().hex[:8]}@example.com"

    res_a = client.post("/api/auth/signup", json={"name": "User A", "email": email_a, "password": "Password123!"})
    token_a = res_a.json()["session_token"]

    res_b = client.post("/api/auth/signup", json={"name": "User B", "email": email_b, "password": "Password456!"})
    token_b = res_b.json()["session_token"]

    # User A creates a conversation
    create_res = client.post(
        "/api/conversations",
        json={"title": "Suspicious Mule Network", "graph_name": "fraud_swiftpay"},
        cookies={"graphos_session": token_a},
    )
    assert create_res.status_code == 200
    conv_id = create_res.json()["conversation"]["id"]

    # User A can retrieve it
    get_a = client.get(f"/api/conversations/{conv_id}", cookies={"graphos_session": token_a})
    assert get_a.status_code == 200
    assert get_a.json()["conversation"]["id"] == conv_id

    # User B CANNOT retrieve User A's conversation (strict isolation -> 404)
    get_b = client.get(f"/api/conversations/{conv_id}", cookies={"graphos_session": token_b})
    assert get_b.status_code == 404

    # User B list conversations does not show User A's conversation
    list_b = client.get("/api/conversations", cookies={"graphos_session": token_b})
    assert list_b.status_code == 200
    assert all(c["id"] != conv_id for c in list_b.json()["conversations"])

    # User A list conversations shows it
    list_a = client.get("/api/conversations", cookies={"graphos_session": token_a})
    assert list_a.status_code == 200
    assert any(c["id"] == conv_id for c in list_a.json()["conversations"])

    # User A deletes it
    del_res = client.delete(f"/api/conversations/{conv_id}", cookies={"graphos_session": token_a})
    assert del_res.status_code == 200

    # User A cannot retrieve it anymore
    assert client.get(f"/api/conversations/{conv_id}", cookies={"graphos_session": token_a}).status_code == 404

