import json
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from server import (
    analyze_graph_impact,
    check_policy,
    execute_approved_action,
    find_shortest_evidence_path,
    get_entity_profile,
    propose_action,
    record_outcome,
    retrieve_source_documents,
    run_graph_algorithm,
    search_connected_entities,
    simulate_action,
    traverse_relationships,
)


def parse(result: str) -> dict:
    return json.loads(result)


def main() -> None:
    print("=================================================================")
    print("Testing Standalone GraphOS MCP Server (/mcp_server)")
    print("=================================================================\n")

    # 1. Search
    print("1. [search_connected_entities]")
    res1 = parse(search_connected_entities("payments", limit=5))
    assert res1["count"] > 0, res1
    print(f"   ✓ Search returned {res1['count']} entities")

    # 2. Profile
    print("\n2. [get_entity_profile]")
    res2 = parse(get_entity_profile("release-payments-2026-10"))
    assert res2["found"], res2
    print(f"   ✓ Entity: {res2['entity']['name']}")

    # 3. Traverse
    print("\n3. [traverse_relationships]")
    res3 = parse(traverse_relationships("release-payments-2026-10", depth=2, limit=5))
    assert res3["count"] > 0, res3
    print(f"   ✓ Discovered {res3['count']} multi-hop paths")

    # 4. Shortest Evidence Path
    print("\n4. [find_shortest_evidence_path]")
    res4 = parse(find_shortest_evidence_path("release-payments-2026-10", "event-liam-leave", max_depth=8))
    assert res4["found"], res4
    print(f"   ✓ Verified path of {res4['hop_count']} hops")

    # 5. Algorithm
    print("\n5. [run_graph_algorithm]")
    pr = parse(run_graph_algorithm("pagerank", top_k=3))
    assert pr["count"] > 0, pr
    print(f"   ✓ PageRank top entity: {pr['ranked_entities'][0]['name']}")

    # 6. Impact
    print("\n6. [analyze_graph_impact]")
    imp = parse(analyze_graph_impact("task-code-review-482", direction="downstream"))
    assert imp["found"], imp
    print(f"   ✓ Blast radius: {imp['blast_radius']['severity']} (score: {imp['blast_radius']['score']})")

    # 7. Source Documents
    print("\n7. [retrieve_source_documents]")
    docs = parse(retrieve_source_documents(["service-payment-api"]))
    assert docs["count"] > 0, docs
    print(f"   ✓ Retrieved {docs['count']} source specs")

    # 8. Check Policy
    print("\n8. [check_policy]")
    pol = parse(check_policy("reassign_review", "task-code-review-482", assignee_id="person-ravi-kulkarni"))
    assert pol["allowed"] is True, pol
    print("   ✓ Reassign policy evaluation: PERMITTED")

    # 9. Simulate Action
    print("\n9. [simulate_action]")
    sim = parse(simulate_action("reassign_review", "task-code-review-482", params={"assignee_id": "person-ravi-kulkarni"}))
    assert sim["risk_assessment"]["allowed_under_current_policy"] is True
    print(f"   ✓ Counterfactual simulation: {sim['risk_assessment']['risk_level']} risk")

    # 10. Propose Action
    print("\n10. [propose_action]")
    prop = parse(
        propose_action(
            action="reassign_review",
            target_id="task-code-review-482",
            rationale="Reassign review to available staff engineer Ravi Kulkarni.",
            evidence_ids=["event-liam-leave"],
            params={"assignee_id": "person-ravi-kulkarni"},
        )
    )
    assert prop["policy_allowed"] is True, prop
    print(f"   ✓ Proposal ID: {prop['proposal_id']}, Token: {prop['approval_token']}")

    # 11. Execute Approved Action
    print("\n11. [execute_approved_action]")
    ex = parse(execute_approved_action(prop["proposal_id"], prop["approval_token"]))
    assert ex["executed"] is True, ex
    print(f"   ✓ Action executed: {ex['execution_id']}")

    # 12. Record Outcome
    print("\n12. [record_outcome]")
    mem = parse(
        record_outcome(
            finding_id="VERIFIED-STANDALONE-TEST",
            target_entity_ids=["task-code-review-482"],
            summary="Verified standalone MCP server operations against FalkorDB Cloud.",
            outcome_status="RESOLVED",
        )
    )
    assert mem["status"] == "SAVED_TO_ORGANIZATIONAL_MEMORY", mem
    print(f"   ✓ Memory ID: {mem['memory_id']}")

    print("\n=================================================================")
    print("ALL 12 TOOLS IN /mcp_server PASSED VERIFICATION!")
    print("=================================================================")


if __name__ == "__main__":
    main()
