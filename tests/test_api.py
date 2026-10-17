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
