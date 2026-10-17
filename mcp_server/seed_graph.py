from __future__ import annotations

import os
import re
from typing import Any

from dotenv import find_dotenv, load_dotenv
from falkordb import FalkorDB

load_dotenv(find_dotenv())

GRAPH_NAME = os.getenv("GRAPHOS_GRAPH_NAME", "graphos_dev")
OBSERVED_AT = "2026-10-15T12:00:00+05:30"


def entity(label: str, entity_id: str, name: str, **props):
    """Create a typed entity with a stable ID and demo source reference."""
    return (
        label,
        {
            "id": entity_id,
            "name": name,
            "kind": label,
            "source_ref": f"demo:{entity_id}",
            **props,
        },
    )


NODES = [
    entity(
        "Project", "project-payments",
        "Payments Platform", status="active"
    ),
    entity(
        "Release", "release-payments-2026-10",
        "Payments Release October 2026",
        status="delayed", target_environment="production"
    ),
    entity(
        "Service", "service-payment-api",
        "Payment API", status="active"
    ),
    entity(
        "Service", "service-checkout",
        "Checkout Service", status="active"
    ),
    entity(
        "Repository", "repo-payment-api",
        "payment-api", default_branch="main"
    ),
    entity(
        "Repository", "repo-checkout",
        "checkout-service", default_branch="main"
    ),
    entity(
        "PullRequest", "pr-482",
        "PR #482: Update payments SDK",
        status="awaiting_review",
        change_summary="Updates the third-party payments SDK"
    ),
    entity(
        "PullRequest", "pr-479",
        "PR #479: Payment error handling",
        status="merged"
    ),
    entity(
        "File", "file-requirements-lock",
        "requirements.lock"
    ),
    entity(
        "File", "file-payment-py",
        "payment.py"
    ),
    entity(
        "File", "file-checkout-py",
        "checkout.py"
    ),
    entity(
        "Dependency", "dep-acme-payments-sdk",
        "acme-payments-sdk",
        current_version="4.1.0",
        proposed_version="4.2.0"
    ),
    entity(
        "Dependency", "dep-requests",
        "requests", current_version="2.32.0"
    ),
    entity(
        "Person", "person-maya-chen",
        "Maya Chen", role="developer", availability="available"
    ),
    entity(
        "Person", "person-liam-patel",
        "Liam Patel", role="reviewer", availability="on_leave"
    ),
    entity(
        "Person", "person-priya-shah",
        "Priya Shah", role="security_reviewer",
        availability="available"
    ),
    entity(
        "Person", "person-ravi-kulkarni",
        "Ravi Kulkarni", role="reviewer", availability="available"
    ),
    entity(
        "Person", "person-oliver-lee",
        "Oliver Lee", role="release_manager",
        availability="available"
    ),
    entity(
        "Team", "team-platform",
        "Platform Engineering"
    ),
    entity(
        "Team", "team-security",
        "Product Security"
    ),
    entity(
        "Task", "task-code-review-482",
        "Review PR #482",
        status="blocked", priority="high"
    ),
    entity(
        "Task", "task-security-review-482",
        "Security review for payments SDK",
        status="open", priority="high"
    ),
    entity(
        "Task", "task-integration-tests",
        "Payments integration tests",
        status="passed"
    ),
    entity(
        "Task", "task-staging-validation",
        "Validate release in staging",
        status="pending"
    ),
    entity(
        "Task", "task-release-approval",
        "Approve production release",
        status="pending"
    ),
    entity(
        "Policy", "policy-third-party-review",
        "Third-Party Dependency Review",
        requirement="Security review required for new dependency versions"
    ),
    entity(
        "Policy", "policy-production-release",
        "Production Release Policy",
        requirement="Required reviews and release approval must be complete"
    ),
    entity(
        "Policy", "policy-emergency-rollback",
        "Emergency Rollback Policy",
        requirement="Rollback requires an authorized operator"
    ),
    entity(
        "Event", "event-liam-leave",
        "Liam Patel is on leave",
        event_date="2026-10-15",
        source_record_id="HR-LEAVE-204"
    ),
    entity(
        "Event", "event-release-delay",
        "Payments release delay reported",
        event_date="2026-10-15",
        source_record_id="INC-902"
    ),
    entity(
        "Document", "doc-release-runbook",
        "Payments Release Runbook",
        source_record_id="DOC-RUNBOOK-12"
    ),
    entity(
        "Document", "doc-security-guide",
        "Dependency Security Review Guide",
        source_record_id="DOC-SEC-07"
    ),
    entity(
        "Document", "doc-pr-482-notes",
        "PR #482 Change Notes",
        source_record_id="DOC-PR-482"
    ),
    entity(
        "Incident", "incident-release-delay",
        "Delayed Payments Release",
        status="open", severity="high"
    ),
    entity(
        "Environment", "env-staging",
        "Staging Environment", status="available"
    ),
    entity(
        "Environment", "env-production",
        "Production Environment", status="protected"
    ),
    entity(
        "Commit", "commit-a13f09c",
        "a13f09c: Update payments SDK"
    ),
    entity(
        "Pipeline", "pipeline-payments-ci",
        "Payments CI Pipeline", status="passed"
    ),
]


EDGES = [
    ("project-payments", "HAS_RELEASE", "release-payments-2026-10"),
    ("project-payments", "HAS_TEAM", "team-platform"),
    ("project-payments", "HAS_TEAM", "team-security"),

    ("release-payments-2026-10", "DEPLOYS", "service-payment-api"),
    ("release-payments-2026-10", "TARGETS_ENV", "env-production"),
    ("release-payments-2026-10", "BLOCKED_BY", "pr-482"),
    ("release-payments-2026-10", "REQUIRES", "task-release-approval"),
    ("release-payments-2026-10", "GOVERNED_BY", "policy-production-release"),

    ("service-payment-api", "IMPLEMENTED_IN", "repo-payment-api"),
    ("service-payment-api", "DEPENDS_ON", "service-checkout"),
    ("service-payment-api", "DEPLOYED_TO", "env-staging"),
    ("service-checkout", "IMPLEMENTED_IN", "repo-checkout"),

    ("repo-payment-api", "HAS_PULL_REQUEST", "pr-482"),
    ("repo-payment-api", "HAS_PULL_REQUEST", "pr-479"),
    ("repo-payment-api", "CONTAINS", "file-payment-py"),
    ("repo-payment-api", "CONTAINS", "file-requirements-lock"),
    ("repo-checkout", "CONTAINS", "file-checkout-py"),

    ("pr-482", "MODIFIES", "file-requirements-lock"),
    ("pr-482", "INTRODUCES_DEPENDENCY", "dep-acme-payments-sdk"),
    ("pr-482", "AUTHORED_BY", "person-maya-chen"),
    ("pr-482", "BLOCKED_BY", "task-code-review-482"),
    ("pr-482", "BLOCKED_BY", "task-security-review-482"),
    ("pr-482", "ASSOCIATED_WITH", "commit-a13f09c"),
    ("pr-482", "CHECKED_BY", "pipeline-payments-ci"),
    ("pr-482", "DOCUMENTED_IN", "doc-pr-482-notes"),

    ("task-code-review-482", "ASSIGNED_TO", "person-liam-patel"),
    ("task-code-review-482", "OWNED_BY", "team-platform"),
    ("person-liam-patel", "HAS_EVENT", "event-liam-leave"),

    ("task-security-review-482", "ASSIGNED_TO", "person-priya-shah"),
    ("task-security-review-482", "OWNED_BY", "team-security"),
    ("policy-third-party-review", "TRIGGERS", "task-security-review-482"),
    ("dep-acme-payments-sdk", "GOVERNED_BY", "policy-third-party-review"),
    ("policy-third-party-review", "DOCUMENTED_IN", "doc-security-guide"),
    ("doc-security-guide", "EXPLAINS", "policy-third-party-review"),

    ("task-release-approval", "ASSIGNED_TO", "person-oliver-lee"),
    ("task-release-approval", "OWNED_BY", "team-platform"),

    ("team-platform", "HAS_MEMBER", "person-maya-chen"),
    ("team-platform", "HAS_MEMBER", "person-liam-patel"),
    ("team-platform", "HAS_MEMBER", "person-ravi-kulkarni"),
    ("team-security", "HAS_MEMBER", "person-priya-shah"),

    ("pr-479", "AUTHORED_BY", "person-ravi-kulkarni"),
    ("pr-479", "MODIFIES", "file-payment-py"),
    ("commit-a13f09c", "PART_OF", "pr-482"),

    ("incident-release-delay", "IMPACTS", "release-payments-2026-10"),
    ("incident-release-delay", "TRACED_TO", "task-code-review-482"),
    ("incident-release-delay", "DOCUMENTED_IN", "doc-release-runbook"),
    ("doc-release-runbook", "COVERS", "service-payment-api"),

    ("pipeline-payments-ci", "RUNS_ON", "env-staging"),
    ("pipeline-payments-ci", "VALIDATES", "repo-payment-api"),
    ("task-integration-tests", "VALIDATES", "pr-482"),
    ("task-staging-validation", "VALIDATES", "release-payments-2026-10"),
    ("task-staging-validation", "ASSIGNED_TO", "person-ravi-kulkarni"),
    ("task-staging-validation", "DEPENDS_ON", "task-security-review-482"),

    ("policy-emergency-rollback", "APPLIES_TO", "service-payment-api"),
    ("dep-requests", "USED_BY", "repo-payment-api"),
]


def main() -> None:
    labels = {label for label, _ in NODES}
    node_ids = {props["id"] for _, props in NODES}

    if len(node_ids) != len(NODES):
        raise ValueError("Duplicate entity IDs found in NODES.")

    for label, props in NODES:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", label):
            raise ValueError(f"Invalid node label: {label}")
        if not props.get("id") or not props.get("name"):
            raise ValueError(f"Entity is missing id or name: {props}")

    for source, rel_type, target in EDGES:
        if source not in node_ids or target not in node_ids:
            raise ValueError(f"Unresolved relationship: {source} -> {target}")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", rel_type):
            raise ValueError(f"Invalid relationship type: {rel_type}")

    host = os.getenv("FALKORDB_HOST", "127.0.0.1")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    username = os.getenv("FALKORDB_USERNAME") or None
    password = os.getenv("FALKORDB_PASSWORD") or None
    ssl_val = os.getenv("FALKORDB_SSL", "false").lower() in ("true", "1", "yes")

    kwargs: dict[str, Any] = {
        "host": host,
        "port": port,
        "ssl": ssl_val,
    }
    if username:
        kwargs["username"] = username
    if password:
        kwargs["password"] = password

    try:
        db = FalkorDB(**kwargs)
        graph = db.select_graph(GRAPH_NAME)
    except Exception:
        if ssl_val:
            kwargs["ssl"] = False
            db = FalkorDB(**kwargs)
            graph = db.select_graph(GRAPH_NAME)
        else:
            raise

    for label, props in NODES:
        graph.query(
            f"""
            MERGE (n:Entity {{id: $id}})
            SET n:{label}
            SET n += $props
            """,
            {"id": props["id"], "props": props},
        )

    for source, rel_type, target in EDGES:
        edge_id = f"{source}__{rel_type.lower()}__{target}"
        edge_props = {
            "id": edge_id,
            "source_record_id": f"demo-evidence:{edge_id}",
            "observed_at": OBSERVED_AT,
            "confidence": 0.98,
        }

        graph.query(
            f"""
            MATCH (source:Entity {{id: $source_id}})
            MATCH (target:Entity {{id: $target_id}})
            MERGE (source)-[r:{rel_type} {{id: $edge_id}}]->(target)
            SET r += $props
            """,
            {
                "source_id": source,
                "target_id": target,
                "edge_id": edge_id,
                "props": edge_props,
            },
        )

    node_result = graph.query(
        "MATCH (n:Entity) RETURN count(n) AS total"
    )
    edge_result = graph.query(
        "MATCH ()-[r]->() RETURN count(r) AS total"
    )

    total_nodes = node_result.result_set[0][0]
    total_edges = edge_result.result_set[0][0]

    print(f"Graph: {GRAPH_NAME}")
    print(f"Seed entities defined: {len(NODES)}")
    print(f"Seed relationships defined: {len(EDGES)}")
    print(f"Total entities in graph: {total_nodes}")
    print(f"Total relationships in graph: {total_edges}")
    print("Graph seed completed successfully.")


if __name__ == "__main__":
    main()
