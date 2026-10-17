from __future__ import annotations

import json
from agent.evidence import EvidenceCollector, EntityFact, RelationshipEdge, EvidencePathChain


def test_evidence_collector_entities_and_profiles() -> None:
    collector = EvidenceCollector()

    search_json = json.dumps({
        "entities": [
            {
                "id": "rel-payments-v2",
                "name": "Payments Service v2.4",
                "kind": "Release",
                "status": "blocked",
                "properties": {"tier": 1},
            }
        ]
    })
    collector.ingest_tool_output("search_connected_entities", {"query": "payments"}, search_json)

    assert "rel-payments-v2" in collector.entities
    fact = collector.entities["rel-payments-v2"]
    assert fact.name == "Payments Service v2.4"
    assert fact.status == "blocked"
    assert fact.classification == "FACT"

    profile_json = json.dumps({
        "entity": {
            "id": "rel-payments-v2",
            "name": "Payments Service v2.4",
            "kind": "Release",
            "properties": {"status": "blocked", "source_ref": "jira-99"},
        },
        "outgoing_relationships": [
            {
                "type": "DEPENDS_ON",
                "target": {"id": "task-sec-review", "name": "Security Review Task", "kind": "Task"},
                "evidence": {"confidence": 0.95, "source_record_id": "rec-123", "observed_at": "2026-10-15T10:00:00Z"},
            }
        ],
    })
    collector.ingest_tool_output("get_entity_profile", {"entity_id": "rel-payments-v2"}, profile_json)

    assert collector.entities["rel-payments-v2"].source_ref == "jira-99"
    assert len(collector.edges) == 1
    edge = collector.edges[0]
    assert edge.from_id == "rel-payments-v2"
    assert edge.relationship_type == "DEPENDS_ON"
    assert edge.to_id == "task-sec-review"
    assert edge.source_record_id == "rec-123"
    assert edge.confidence == 0.95


def test_evidence_collector_paths_and_chains() -> None:
    collector = EvidenceCollector()

    path_json = json.dumps({
        "found": True,
        "source_id": "rel-payments-v2",
        "target_id": "usr-alice",
        "hop_count": 2,
        "path_nodes": [
            {"id": "rel-payments-v2", "name": "Payments Service v2.4"},
            {"id": "task-sec-review", "name": "Security Review Task"},
            {"id": "usr-alice", "name": "Alice Smith"},
        ],
        "path_edges": [
            {"type": "DEPENDS_ON", "from_id": "rel-payments-v2", "to_id": "task-sec-review"},
            {"type": "ASSIGNED_TO", "from_id": "task-sec-review", "to_id": "usr-alice"},
        ],
    })
    collector.ingest_tool_output(
        "find_shortest_evidence_path",
        {"source_id": "rel-payments-v2", "target_id": "usr-alice"},
        path_json,
    )

    assert len(collector.paths) == 1
    p = collector.paths[0]
    assert p.source_id == "rel-payments-v2"
    assert p.target_id == "usr-alice"
    assert p.hop_count == 2
    assert p.chain_names == ["Payments Service v2.4", "Security Review Task", "Alice Smith"]


def test_evidence_collector_policy_results_and_summary() -> None:
    collector = EvidenceCollector()

    policy_json = json.dumps({
        "action": "deploy_release",
        "target_id": "rel-payments-v2",
        "verdict": "DENY",
        "allowed": False,
        "reason": "Security review has not been completed.",
        "violated_rules": ["POL-SEC-001"],
        "missing_prerequisites": ["task-sec-review"],
    })
    collector.ingest_tool_output("check_policy", {"action": "deploy_release", "target_id": "rel-payments-v2"}, policy_json)

    assert len(collector.policy_results) == 1
    assert collector.policy_results[0]["allowed"] is False
    assert collector.policy_results[0]["verdict"] == "DENY"

    collector.unresolved_gaps.append("Unknown downstream dependencies for DB replica")

    summary = collector.generate_summary()
    assert summary["total_entities_verified"] == 0
    assert len(summary["policy_evaluations"]) == 1
    assert summary["policy_evaluations"][0]["action"] == "deploy_release"
    assert "Unknown downstream dependencies for DB replica" in summary["unresolved_gaps"]
