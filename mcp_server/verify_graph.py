from __future__ import annotations

import os
from typing import Any

from dotenv import find_dotenv, load_dotenv
from falkordb import FalkorDB

load_dotenv(find_dotenv())

GRAPH_NAME = os.getenv("GRAPHOS_GRAPH_NAME", "graphos_dev")


def main() -> None:
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

    print("\n=== Investigation 1: Review bottleneck ===")

    result = graph.query("""
        MATCH
          (release:Entity {id: 'release-payments-2026-10'})
          -[:DEPLOYS]->(service:Entity)
          -[:IMPLEMENTED_IN]->(repo:Entity)
          -[:HAS_PULL_REQUEST]->(pr:Entity {id: 'pr-482'})
          -[:BLOCKED_BY]->(task:Entity {id: 'task-code-review-482'})
          -[:ASSIGNED_TO]->(reviewer:Entity)
          -[:HAS_EVENT]->(leave:Entity)
        RETURN
          release.name,
          pr.name,
          task.status,
          reviewer.name,
          reviewer.availability,
          leave.name
    """)

    for row in result.result_set:
        print("Release:", row[0])
        print("Pull request:", row[1])
        print("Review task status:", row[2])
        print("Assigned reviewer:", row[3])
        print("Reviewer availability:", row[4])
        print("Related event:", row[5])

    print("\n=== Investigation 2: Dependency policy ===")

    result = graph.query("""
        MATCH
          (pr:Entity {id: 'pr-482'})
          -[:INTRODUCES_DEPENDENCY]->(dep:Entity)
          -[:GOVERNED_BY]->(policy:Entity)
        RETURN pr.name, dep.name, dep.proposed_version, policy.name
    """)

    for row in result.result_set:
        print("Pull request:", row[0])
        print("Dependency:", row[1])
        print("Proposed version:", row[2])
        print("Applicable policy:", row[3])

    print("\n=== Investigation 3: Pending security review ===")

    result = graph.query("""
        MATCH
          (pr:Entity {id: 'pr-482'})
          -[:BLOCKED_BY]->(task:Entity {id: 'task-security-review-482'})
          -[:ASSIGNED_TO]->(reviewer:Entity)
        RETURN pr.name, task.name, task.status, reviewer.name
    """)

    for row in result.result_set:
        print("Pull request:", row[0])
        print("Required task:", row[1])
        print("Task status:", row[2])
        print("Assigned reviewer:", row[3])


if __name__ == "__main__":
    main()
