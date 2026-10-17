from __future__ import annotations

import json
from typing import Any, Callable, Optional

from agent.models import ChatMessage, ProviderResponse, ToolCall, ToolDefinition
from agent.providers.base import BaseLLMProvider


class MockProvider(BaseLLMProvider):
    """
    Deterministic provider for automated testing and offline development.
    Can be scripted with explicit responses or use an investigative heuristic
    to verify multi-step MCP execution against FalkorDB.
    """

    def __init__(
        self,
        canned_responses: Optional[list[ProviderResponse]] = None,
        model_name: str = "mock-investigator-v1",
    ) -> None:
        self.canned_responses = list(canned_responses or [])
        self.model_name = model_name
        self.call_history: list[list[ChatMessage]] = []
        self.step_counter = 0

    def get_model_info(self) -> dict[str, Any]:
        return {
            "provider": "mock",
            "model": self.model_name,
            "api_base": "mock://memory",
            "api_key_configured": True,
        }

    async def validate_connection(self) -> tuple[bool, str]:
        return True, "Mock provider initialized and active in-memory."

    async def generate_response(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
    ) -> ProviderResponse:
        self.call_history.append(list(messages))
        self.step_counter += 1

        if self.canned_responses:
            return self.canned_responses.pop(0)

        user_query = ""
        user_msg_idx = -1
        for idx in range(len(messages) - 1, -1, -1):
            if messages[idx].role == "user" and messages[idx].content:
                user_query = messages[idx].content
                user_msg_idx = idx
                break

        turn_step = sum(
            1 for m in messages[user_msg_idx + 1 :] if m.role == "assistant"
        ) + 1

        clean_query = user_query
        if "CURRENT USER OBJECTIVE:" in user_query:
            clean_query = user_query.split("CURRENT USER OBJECTIVE:", 1)[1].split("\n\nInstructions:", 1)[0].strip()
        elif "INVESTIGATION OBJECTIVE:" in user_query:
            clean_query = user_query.split("INVESTIGATION OBJECTIVE:", 1)[1].split("\n\nPlease inspect", 1)[0].strip()

        cq_lower = clean_query.lower()

        if "audit" in cq_lower:
            if turn_step == 1:
                return ProviderResponse(
                    content="Let me retrieve the entity profile for the specified audit record.",
                    tool_calls=[
                        ToolCall(
                            id="call_mock_audit_1",
                            function_name="get_entity_profile",
                            arguments={"entity_id": "audit-rec-901"},
                        )
                    ],
                )
            elif turn_step == 2:
                return ProviderResponse(
                    content="The profile shows zero connected relationships. Let me inspect its neighbors to confirm whether it is completely isolated.",
                    tool_calls=[
                        ToolCall(
                            id="call_mock_audit_2",
                            function_name="inspect_entity_neighbors",
                            arguments={"entity_id": "audit-rec-901", "direction": "both"},
                        )
                    ],
                )
            else:
                return ProviderResponse(
                    content=(
                        "### Investigation Finding: Isolated Audit Record\n\n"
                        "Inspection of record `audit-rec-901` confirms it exists in the graph with properties but has **0 incoming and 0 outgoing relationships**.\n\n"
                        "#### Record Details:\n"
                        "- Entity Identifier: `audit-rec-901`\n"
                        "- Isolation Status: Verified Isolated (complete neighbor inspection returned 0 adjacent nodes)\n"
                        "- Findings: This record is standalone and does not have dependencies or impacts on any software release or payment components."
                    ),
                    tool_calls=[],
                    finish_reason="stop",
                )

        elif "quantum" in cq_lower:
            if turn_step == 1:
                return ProviderResponse(
                    content="Let me search the knowledge graph for 'QuantumTeleportation' to verify entity records.",
                    tool_calls=[
                        ToolCall(
                            id="call_mock_unknown",
                            function_name="search_connected_entities",
                            arguments={"query": "QuantumTeleportation", "limit": 5},
                        )
                    ],
                )
            else:
                return ProviderResponse(
                    content=(
                        "### Investigation Finding: Insufficient Graph Evidence\n\n"
                        "After querying the GraphOS knowledge graph using `search_connected_entities`, **no connected entities found** matching the requested entity.\n\n"
                        "#### Grounded Fact Findings:\n"
                        "- Total entities found: 0\n"
                        "- Total dependency paths: 0\n\n"
                        "#### Unresolved Questions & Uncertainty:\n"
                        "- The target entity does not exist in the active FalkorDB instance.\n"
                        "- Absence of graph paths and records confirms there is insufficient evidence to determine or hypothesize a blocker.\n"
                        "- As an evidence-bound investigator, I report this gap rather than inventing or fabricating relationships."
                    ),
                    tool_calls=[],
                    finish_reason="stop",
                )

        elif "payments" in cq_lower:
            if turn_step == 1:
                return ProviderResponse(
                    content="I will search for the payments release entity in the graph to inspect its status.",
                    tool_calls=[
                        ToolCall(
                            id="call_mock_1",
                            function_name="search_connected_entities",
                            arguments={"query": "payments", "limit": 5},
                        )
                    ],
                )
            elif turn_step == 2:
                return ProviderResponse(
                    content="Entity 'release-payments-2026-10' was found. Let me inspect its profile and relationships.",
                    tool_calls=[
                        ToolCall(
                            id="call_mock_2",
                            function_name="get_entity_profile",
                            arguments={"entity_id": "release-payments-2026-10"},
                        )
                    ],
                )
            elif turn_step == 3:
                return ProviderResponse(
                    content="The release deploys 'service-payment-api', which points to 'pr-482'. Let me inspect the blockers on PR 482.",
                    tool_calls=[
                        ToolCall(
                            id="call_mock_3",
                            function_name="traverse_relationships",
                            arguments={"entity_id": "pr-482", "depth": 2, "limit": 10},
                        )
                    ],
                )
            elif turn_step == 4:
                return ProviderResponse(
                    content="PR 482 is blocked by review task 'task-code-review-482' and security task 'task-security-review-482'. Let me check the assignee 'person-liam-patel'.",
                    tool_calls=[
                        ToolCall(
                            id="call_mock_4",
                            function_name="get_entity_profile",
                            arguments={"entity_id": "person-liam-patel"},
                        )
                    ],
                )
            else:
                return ProviderResponse(
                    content=(
                        "### Executive Summary: Root Cause Analysis for Payments Release Delay\n\n"
                        "Based on verified multi-hop evidence from the GraphOS knowledge graph, the **Payments Release October 2026** "
                        "(`release-payments-2026-10`) is currently delayed due to an unresolved review bottleneck on **PR #482** "
                        "(`pr-482: Update payments SDK`).\n\n"
                        "#### Supporting Graph Evidence Chain:\n"
                        "1. **Release Target**: `release-payments-2026-10` (status: `delayed`) -> `DEPLOYS` -> `service-payment-api`\n"
                        "2. **Repository & Pull Request**: `service-payment-api` -> `IMPLEMENTED_IN` -> `repo-payment-api` -> `HAS_PULL_REQUEST` -> `pr-482` (status: `awaiting_review`)\n"
                        "3. **Blocking Code Review Task**: `pr-482` -> `BLOCKED_BY` -> `task-code-review-482` (status: `in_progress`)\n"
                        "4. **Reviewer Absence**: `task-code-review-482` -> `ASSIGNED_TO` -> `person-liam-patel` (availability: `on_leave`) -> `HAS_EVENT` -> `event-liam-leave` ('Liam Patel is on leave')\n"
                        "5. **Unresolved Security Review**: `pr-482` is concurrently blocked by `task-security-review-482` (status: `in_progress`) assigned to `person-priya-shah`\n\n"
                        "#### Actionable Remediation:\n"
                        "Reassign `task-code-review-482` to an available peer reviewer (e.g. staff engineer Ravi Kulkarni) using the governance-permitted `reassign_review` workflow."
                    ),
                    tool_calls=[],
                    finish_reason="stop",
                )

        elif any(w in cq_lower for w in ["replace", "reviewer", "reassign", "patel", "kulkarni", "candidate"]):
            if turn_step == 1:
                return ProviderResponse(
                    content="Let me check the organization's review reassignment policy and find eligible candidate reviewers.",
                    tool_calls=[
                        ToolCall(
                            id="call_mock_policy",
                            function_name="check_policy",
                            arguments={"policy_name": "reassign_review", "target_role": "Staff Engineer"},
                        )
                    ],
                )
            elif turn_step == 2:
                return ProviderResponse(
                    content="The policy permits review reassignment to a Staff Engineer. Let me inspect candidate 'person-ravi-kulkarni'.",
                    tool_calls=[
                        ToolCall(
                            id="call_mock_profile_ravi",
                            function_name="get_entity_profile",
                            arguments={"entity_id": "person-ravi-kulkarni"},
                        )
                    ],
                )
            else:
                return ProviderResponse(
                    content=(
                        "### Follow-up Finding: Eligible Replacement Reviewer\n\n"
                        "Based on the knowledge graph and governance policies:\n\n"
                        "1. **Policy Permitted**: Under `policy-code-review-reassignment`, reassigning a blocked review "
                        "task from an engineer on leave to an active peer of equal or senior grade is **PERMITTED**.\n"
                        "2. **Candidate Verified**: Staff Engineer **Ravi Kulkarni** (`person-ravi-kulkarni`) is currently "
                        "`active` and possesses domain authorization on `service-payment-api`.\n"
                        "3. **Proposed Action**: Reassigning `task-code-review-482` to Ravi Kulkarni will directly unblock "
                        "the review path for PR #482 without violating compliance bounds."
                    ),
                    tool_calls=[],
                    finish_reason="stop",
                )

        elif any(w in cq_lower for w in ["shortest path", "evidence chain", "path from"]):
            if turn_step == 1:
                return ProviderResponse(
                    content="Let me trace the verified shortest evidence path from the payments release to Liam Patel's leave event.",
                    tool_calls=[
                        ToolCall(
                            id="call_mock_path",
                            function_name="find_shortest_evidence_path",
                            arguments={
                                "source_id": "release-payments-2026-10",
                                "target_id": "event-liam-leave",
                                "max_depth": 8,
                            },
                        )
                    ],
                )
            else:
                return ProviderResponse(
                    content=(
                        "### Verified Evidence Path\n\n"
                        "The GraphOS shortest path algorithm established a verified 4-hop dependency chain:\n\n"
                        "```text\n"
                        "[release-payments-2026-10] (Payments Release October 2026)\n"
                        "   └── DEPLOYS ──> [service-payment-api] (Payment API Service)\n"
                        "        └── IMPLEMENTED_IN ──> [repo-payment-api] (Payment API Repo)\n"
                        "             └── HAS_PULL_REQUEST ──> [pr-482] (Update payments SDK)\n"
                        "                  └── BLOCKED_BY ──> [task-code-review-482] (Code Review #482)\n"
                        "                       └── ASSIGNED_TO ──> [person-liam-patel] (Liam Patel)\n"
                        "                            └── HAS_EVENT ──> [event-liam-leave] (Liam Patel is on leave)\n"
                        "```\n\n"
                        "Confidence score for each traversed edge is 1.0 (verified from production Git & HR records)."
                    ),
                    tool_calls=[],
                    finish_reason="stop",
                )


        elif any(w in cq_lower for w in ["supply", "supplier", "warehouse", "ships_to", "used_in", "shipping"]):
            if turn_step == 1:
                return ProviderResponse(
                    content="Let me search the knowledge graph for supplier entities to trace downstream component dependencies.",
                    tool_calls=[
                        ToolCall(
                            id="call_mock_supply_search",
                            function_name="search_connected_entities",
                            arguments={"query": "supplier", "limit": 5},
                        )
                    ],
                )
            elif turn_step == 2:
                return ProviderResponse(
                    content="Found supplier 'supplier-apex-logistics'. Let me traverse downstream relationships to identify stored components and impacted products.",
                    tool_calls=[
                        ToolCall(
                            id="call_mock_supply_traverse",
                            function_name="traverse_relationships",
                            arguments={"entity_id": "supplier-apex-logistics", "depth": 3, "limit": 15},
                        )
                    ],
                )
            else:
                return ProviderResponse(
                    content=(
                        "### Executive Summary: Supply Chain Impact Analysis\n\n"
                        "Based on verified multi-hop evidence from the connected knowledge graph, if supplier "
                        "**Apex Logistics** (`supplier-apex-logistics`) stops shipping, **2 downstream products** "
                        "(`prod-smart-sensor-v2` and `prod-telemetry-gateway`) could be directly impacted.\n\n"
                        "#### Supporting Graph Evidence Chain:\n"
                        "1. `supplier-apex-logistics` ➔ `SHIPS_TO` ➔ `warehouse-rotterdam` (Capacity: 85%)\n"
                        "2. `warehouse-rotterdam` ➔ `STORES` ➔ `comp-microcontroller-arm` (Lead time: 45 days)\n"
                        "3. `comp-microcontroller-arm` ➔ `USED_IN` ➔ `prod-smart-sensor-v2`\n"
                        "4. `comp-microcontroller-arm` ➔ `USED_IN` ➔ `prod-telemetry-gateway`\n\n"
                        "#### Unresolved Questions & Uncertainty:\n"
                        "- Buffer stock levels at `warehouse-rotterdam` are not recorded in the graph.\n"
                        "- Alternate supplier routes have not been registered."
                    ),
                    tool_calls=[],
                    finish_reason="stop",
                )

        elif any(w in cq_lower for w in ["account", "transfers_to", "transaction", "fraud", "network", "device"]):
            if turn_step == 1:
                return ProviderResponse(
                    content="Let me trace the shortest path between the two financial accounts to discover intermediate transfer hops and shared devices.",
                    tool_calls=[
                        ToolCall(
                            id="call_mock_fin_path",
                            function_name="find_shortest_evidence_path",
                            arguments={"source_id": "acc-mule-881", "target_id": "acc-target-902", "max_depth": 6},
                        )
                    ],
                )
            else:
                return ProviderResponse(
                    content=(
                        "### Executive Summary: Financial Transfer & Device Link Analysis\n\n"
                        "Based on verified multi-hop transaction evidence, account `acc-mule-881` connects to `acc-target-902` "
                        "via a 3-hop transfer chain and a shared hardware device fingerprint.\n\n"
                        "#### Supporting Graph Evidence Chain:\n"
                        "1. `acc-mule-881` ➔ `TRANSFERS_TO` ➔ `acc-intermediary-440` (Txn: `$48,500`)\n"
                        "2. `acc-intermediary-440` ➔ `TRANSFERS_TO` ➔ `acc-target-902` (Txn: `$47,900`)\n"
                        "3. Concurrently: `acc-mule-881` ➔ `OWNS` ➔ `device-uuid-9918` ➔ `CONNECTS_TO` ➔ `network-tor-exit-12`\n\n"
                        "#### Grounded Fact Findings:\n"
                        "- Original transaction IDs and timestamps verified.\n"
                        "- No currency conversion discrepancies detected."
                    ),
                    tool_calls=[],
                    finish_reason="stop",
                )

        elif any(w in cq_lower for w in ["microservice", "infrastructure", "databaseinstance", "cluster", "outage"]):
            if turn_step == 1:
                return ProviderResponse(
                    content="Let me compute the blast radius and downstream dependency impact on the infrastructure graph.",
                    tool_calls=[
                        ToolCall(
                            id="call_mock_infra_impact",
                            function_name="analyze_graph_impact",
                            arguments={"root_entity_id": "svc-auth-core", "direction": "downstream", "max_depth": 3},
                        )
                    ],
                )
            else:
                return ProviderResponse(
                    content=(
                        "### Executive Summary: Cloud Infrastructure Blast Radius\n\n"
                        "A failure in core authentication microservice `svc-auth-core` impacts **3 downstream services** "
                        "and 1 primary database instance in `region-eu-central-1`.\n\n"
                        "#### Supporting Graph Evidence Chain:\n"
                        "1. `svc-auth-core` ➔ `CONNECTS_TO` ➔ `db-user-credentials-primary`\n"
                        "2. `svc-order-processing` ➔ `DEPENDS_ON` ➔ `svc-auth-core`\n"
                        "3. `svc-billing-api` ➔ `DEPENDS_ON` ➔ `svc-auth-core`\n"
                        "4. `db-user-credentials-primary` ➔ `HOSTED_IN` ➔ `region-eu-central-1`"
                    ),
                    tool_calls=[],
                    finish_reason="stop",
                )

        else:
            if turn_step == 1:
                query_term = clean_query[:30].strip() or "general"
                return ProviderResponse(
                    content=f"Let me search the knowledge graph for '{query_term}' to verify entity records.",
                    tool_calls=[
                        ToolCall(
                            id="call_mock_general",
                            function_name="search_connected_entities",
                            arguments={"query": query_term, "limit": 5},
                        )
                    ],
                )
            else:
                return ProviderResponse(
                    content=(
                        f"### Investigation Finding for: {clean_query}\n\n"
                        "Queried connected entities in the knowledge graph. "
                        "Found relevant graph context and verified relationships across connected systems."
                    ),
                    tool_calls=[],
                    finish_reason="stop",
                )
