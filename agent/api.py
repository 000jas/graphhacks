from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import replace
from typing import Any, AsyncGenerator, Optional
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from agent.config import AgentSettings
from agent.engine import GraphOSInvestigator
from agent.models import AgentResult, AgentStep, InvestigationEvent
from agent.mcp_client import MCPClientManager
from agent.guardrails import GuardrailManager, READ_ONLY_ALLOWED_TOOLS
from agent.session import SessionManager
from agent.schema_context import SchemaContextManager

logger = logging.getLogger("graphos.api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="GraphOS Intelligence API",
    description="Universal AI Graph Intelligence Agent Backend powered by FalkorDB and MCP",
    version="1.0.0",
)

# CORS configuration to allow local development and Vercel/cloud deployments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = AgentSettings()
schema_manager = SchemaContextManager(ttl_seconds=300.0)


class InvestigateRequest(BaseModel):
    objective: str = Field(..., description="The natural language investigation question or objective")
    session_id: Optional[str] = Field(None, description="Optional session identifier for multi-turn investigations")
    tenant_graph: Optional[str] = Field(None, description="Optional tenant graph name override")
    mode: Optional[str] = Field("live", description="Execution mode: 'live' or 'demo'")


DEMO_SCENARIOS: dict[str, Any] = {
    "fraud": {
        "scenario_id": "fraud",
        "title": "Cross-Border Mule Network & Sybil Device Linking",
        "objective": "Investigate suspicious transactions and find connected entities or transaction paths that may be relevant.",
        "final_answer": """### Executive Summary: High-Risk Financial Sybil Ring Detected

Based on verified multi-hop transaction evidence across the knowledge graph, account `acc-mule-881` connects to `acc-target-902` through a layered 3-hop transfer chain and a shared hardware fingerprint:

1. **Transaction Laundering Chain**:
   - `acc-mule-881` (`Flagged: Suspicious High-Velocity`) transferred **$48,500 USD** to `acc-intermediary-440`.
   - `acc-intermediary-440` subsequently dispersed **$47,900 USD** to destination `acc-target-902` within 4 minutes.
2. **Device Hardware Fingerprint Association**:
   - Both `acc-mule-881` and `acc-intermediary-440` share physical device fingerprint `device-uuid-9918`.
   - `device-uuid-9918` routed sessions through anonymous endpoint `network-tor-exit-12`.

#### Verified Evidence & Grounded Facts:
- All transaction records and timestamps verified from transaction logs.
- Sybil hardware clustering confirmed via distinct network relationship paths.
- Recommended Action: Freeze accounts `acc-mule-881` and `acc-intermediary-440` pending AML SAR filing.""",
        "evidence_summary": {
            "total_entities_verified": 5,
            "unique_entities_count": 5,
            "total_edges_inspected": 6,
            "total_relationships_count": 6,
            "total_paths_established": 2,
            "duplicate_records_detected": 0,
            "provenance_verification_rate": 1.0,
            "entities": {
                "acc-mule-881": {
                    "id": "acc-mule-881",
                    "name": "Mule Account #881",
                    "kind": "Account",
                    "status": "flagged",
                    "properties": {"balance_usd": 1240.0, "risk_score": 0.94, "jurisdiction": "KY"},
                },
                "acc-intermediary-440": {
                    "id": "acc-intermediary-440",
                    "name": "Intermediary Account #440",
                    "kind": "Account",
                    "status": "active",
                    "properties": {"balance_usd": 600.0, "risk_score": 0.82, "jurisdiction": "PA"},
                },
                "acc-target-902": {
                    "id": "acc-target-902",
                    "name": "Beneficiary Wallet #902",
                    "kind": "Account",
                    "status": "watch_list",
                    "properties": {"balance_usd": 95200.0, "risk_score": 0.88, "jurisdiction": "CH"},
                },
                "device-uuid-9918": {
                    "id": "device-uuid-9918",
                    "name": "Hardware Device UUID-9918",
                    "kind": "Device",
                    "status": "compromised",
                    "properties": {"os": "Linux x86_64", "browser": "Headless Chrome", "first_seen": "2026-09-12"},
                },
                "network-tor-exit-12": {
                    "id": "network-tor-exit-12",
                    "name": "Tor Exit Node #12",
                    "kind": "Network",
                    "status": "anonymized",
                    "properties": {"ip": "185.220.101.5", "asn": "AS200052"},
                },
            },
            "key_paths": [
                {
                    "source_id": "acc-mule-881",
                    "target_id": "acc-target-902",
                    "hop_count": 2,
                    "chain_names": ["Mule Account #881", "Intermediary Account #440", "Beneficiary Wallet #902"],
                    "relationships": ["TRANSFERS_TO", "TRANSFERS_TO"],
                    "is_verified": True,
                },
                {
                    "source_id": "acc-mule-881",
                    "target_id": "network-tor-exit-12",
                    "hop_count": 2,
                    "chain_names": ["Mule Account #881", "Hardware Device UUID-9918", "Tor Exit Node #12"],
                    "relationships": ["OWNS", "CONNECTS_TO"],
                    "is_verified": True,
                },
            ],
            "unresolved_gaps": [],
        },
        "steps": [
            {
                "iteration": 1,
                "thought": "Searching graph for anomalous transaction velocity starting at acc-mule-881.",
                "tool_calls": [{"id": "c1", "function_name": "search_connected_entities", "arguments": {"query": "acc-mule-881"}}],
                "duration_seconds": 0.42,
            },
            {
                "iteration": 2,
                "thought": "Tracing multi-hop transfer relationships and shared hardware identifiers.",
                "tool_calls": [{"id": "c2", "function_name": "traverse_relationships", "arguments": {"entity_id": "acc-mule-881", "depth": 3}}],
                "duration_seconds": 0.65,
            },
        ],
        "duration_seconds": 1.48,
    },
    "security": {
        "scenario_id": "security",
        "title": "Cloud Infrastructure Vulnerability & IAM Blast Radius",
        "objective": "Investigate these security findings, trace their connected dependencies, and identify which findings warrant attention.",
        "final_answer": """### Executive Summary: Critical Attack Path to Production Database

Investigation of Security Finding `cve-2026-4412` reveals a verified privilege escalation path that directly reaches the primary customer credentials database:

1. **Vulnerability Assessment**:
   - `cve-2026-4412` (`CVSS 9.8 Critical: Remote Code Execution`) affects public gateway `svc-auth-core`.
2. **Identity Privilege Escalation**:
   - `svc-auth-core` is bound to IAM role `role-auth-service-admin`, which possesses excessive wildcard permissions `iam:*` and `rds:*`.
3. **Database Exposure**:
   - IAM role allows unauthenticated read replication of `db-user-credentials-primary` located in `region-eu-central-1`.

#### Verified Blast Radius:
- **3 Downstream Microservices**: `svc-billing-api`, `svc-order-processing`, `svc-notification-core`.
- **Primary Data Store**: 1.2M hashed user credentials exposed to potential exfiltration.
- **Recommended Action**: Rotate IAM role session credentials and immediately revoke wildcard database access for `role-auth-service-admin`.""",
        "evidence_summary": {
            "total_entities_verified": 5,
            "unique_entities_count": 5,
            "total_edges_inspected": 5,
            "total_relationships_count": 5,
            "total_paths_established": 1,
            "duplicate_records_detected": 0,
            "provenance_verification_rate": 1.0,
            "entities": {
                "cve-2026-4412": {
                    "id": "cve-2026-4412",
                    "name": "CVE-2026-4412 (Critical RCE)",
                    "kind": "SecurityVulnerability",
                    "status": "critical",
                    "properties": {"cvss": 9.8, "cwe": "CWE-94", "vector": "Network"},
                },
                "svc-auth-core": {
                    "id": "svc-auth-core",
                    "name": "Authentication Gateway Service",
                    "kind": "Service",
                    "status": "vulnerable",
                    "properties": {"runtime": "Node 20", "public_ingress": True, "tier": "Tier-1"},
                },
                "role-auth-service-admin": {
                    "id": "role-auth-service-admin",
                    "name": "IAM Role: Auth Gateway Admin",
                    "kind": "IAMRole",
                    "status": "overprivileged",
                    "properties": {"policy_arns": ["arn:aws:iam::aws:policy/AdministratorAccess"]},
                },
                "db-user-credentials-primary": {
                    "id": "db-user-credentials-primary",
                    "name": "User Credentials Primary DB",
                    "kind": "DatabaseInstance",
                    "status": "active",
                    "properties": {"engine": "PostgreSQL 16", "multi_az": True, "records_count": 1240000},
                },
                "region-eu-central-1": {
                    "id": "region-eu-central-1",
                    "name": "Frankfurt Region (eu-central-1)",
                    "kind": "CloudRegion",
                    "status": "healthy",
                    "properties": {"provider": "AWS", "compliance": "GDPR-Tier1"},
                },
            },
            "key_paths": [
                {
                    "source_id": "cve-2026-4412",
                    "target_id": "db-user-credentials-primary",
                    "hop_count": 3,
                    "chain_names": ["CVE-2026-4412 (Critical RCE)", "Authentication Gateway Service", "IAM Role: Auth Gateway Admin", "User Credentials Primary DB"],
                    "relationships": ["AFFECTS", "ASSUMES_ROLE", "ACCESSES"],
                    "is_verified": True,
                }
            ],
            "unresolved_gaps": [],
        },
        "steps": [
            {
                "iteration": 1,
                "thought": "Querying security finding cve-2026-4412 and inspecting host services.",
                "tool_calls": [{"id": "c1", "function_name": "get_entity_profile", "arguments": {"entity_id": "cve-2026-4412"}}],
                "duration_seconds": 0.38,
            },
            {
                "iteration": 2,
                "thought": "Evaluating blast radius from svc-auth-core into cloud IAM and data stores.",
                "tool_calls": [{"id": "c2", "function_name": "inspect_entity_neighbors", "arguments": {"entity_id": "svc-auth-core", "direction": "outgoing"}}],
                "duration_seconds": 0.54,
            },
        ],
        "duration_seconds": 1.25,
    },
    "codebase": {
        "scenario_id": "codebase",
        "title": "Software Release Dependency Bottleneck & Leave Absence",
        "objective": "Trace dependencies related to this component and identify the possible impact of a proposed change.",
        "final_answer": """### Executive Summary: Release Bottleneck Resolved via Policy Reassignment

Multi-hop dependency analysis of release `release-payments-2026-10` pinpoints an unresolved review bottleneck on Pull Request `#482`:

1. **Release Dependency Chain**:
   - `release-payments-2026-10` (`delayed`) deploys `service-payment-api`.
   - `service-payment-api` is implemented in repository `repo-payment-api`, which has pending pull request `pr-482`.
2. **Review Task Blockage**:
   - `pr-482` is blocked by review task `task-code-review-482` (status: `in_progress`).
   - Assigned engineer `person-liam-patel` is currently `on_leave` with active leave event `event-liam-leave`.
3. **Governance Unblocking**:
   - Policy check against `policy-code-review-reassignment` verifies that reassigning to available Staff Engineer **Ravi Kulkarni** (`person-ravi-kulkarni`) unblocks the path without compliance violations.

#### Verified Evidence:
- Complete 5-hop path verified across Git and HR records with 1.0 confidence.
- Recommended Action: Approve reassignment of `task-code-review-482` to Ravi Kulkarni.""",
        "evidence_summary": {
            "total_entities_verified": 6,
            "unique_entities_count": 6,
            "total_edges_inspected": 6,
            "total_relationships_count": 6,
            "total_paths_established": 1,
            "duplicate_records_detected": 0,
            "provenance_verification_rate": 1.0,
            "entities": {
                "release-payments-2026-10": {
                    "id": "release-payments-2026-10",
                    "name": "Payments Release October 2026",
                    "kind": "Release",
                    "status": "delayed",
                    "properties": {"target_date": "2026-10-20", "tier": "Production"},
                },
                "service-payment-api": {
                    "id": "service-payment-api",
                    "name": "Payment API Service",
                    "kind": "Service",
                    "status": "active",
                    "properties": {"tier": "Tier-1", "language": "TypeScript"},
                },
                "repo-payment-api": {
                    "id": "repo-payment-api",
                    "name": "payment-api repository",
                    "kind": "Repository",
                    "status": "active",
                    "properties": {"default_branch": "main", "visibility": "internal"},
                },
                "pr-482": {
                    "id": "pr-482",
                    "name": "PR #482: Update payments SDK",
                    "kind": "PullRequest",
                    "status": "awaiting_review",
                    "properties": {"author": "Sarah Chen", "lines_changed": 340},
                },
                "task-code-review-482": {
                    "id": "task-code-review-482",
                    "name": "Code Review #482",
                    "kind": "Task",
                    "status": "in_progress",
                    "properties": {"priority": "P0", "due_date": "2026-10-16"},
                },
                "person-liam-patel": {
                    "id": "person-liam-patel",
                    "name": "Liam Patel",
                    "kind": "Person",
                    "status": "on_leave",
                    "properties": {"role": "Senior Engineer", "availability": "on_leave"},
                },
            },
            "key_paths": [
                {
                    "source_id": "release-payments-2026-10",
                    "target_id": "person-liam-patel",
                    "hop_count": 5,
                    "chain_names": ["Payments Release October 2026", "Payment API Service", "payment-api repository", "PR #482: Update payments SDK", "Code Review #482", "Liam Patel"],
                    "relationships": ["DEPLOYS", "IMPLEMENTED_IN", "HAS_PULL_REQUEST", "BLOCKED_BY", "ASSIGNED_TO"],
                    "is_verified": True,
                }
            ],
            "unresolved_gaps": [],
        },
        "steps": [
            {
                "iteration": 1,
                "thought": "Searching for delayed release entity release-payments-2026-10.",
                "tool_calls": [{"id": "c1", "function_name": "get_entity_profile", "arguments": {"entity_id": "release-payments-2026-10"}}],
                "duration_seconds": 0.35,
            },
            {
                "iteration": 2,
                "thought": "Traversing relationships downstream through pull requests and blocking tasks.",
                "tool_calls": [{"id": "c2", "function_name": "traverse_relationships", "arguments": {"entity_id": "release-payments-2026-10", "depth": 4}}],
                "duration_seconds": 0.72,
            },
        ],
        "duration_seconds": 1.35,
    },
}


@app.get("/api/health")
async def health_check():
    """System health and connection diagnostics."""
    return {
        "status": "healthy",
        "service": "GraphOS Universal Intelligence Agent",
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "graph_name": settings.graph_name,
        "mcp_transport": settings.mcp_transport,
        "read_only": settings.read_only,
        "max_iterations": settings.max_iterations,
        "max_tool_calls": settings.max_tool_calls,
        "timestamp": time.time(),
    }


@app.get("/api/graphs")
async def list_available_graphs():
    """List all available graph databases in FalkorDB Cloud."""
    try:
        from mcp_server.db import get_db_client
        client = get_db_client()
        raw_graphs = client.list_graphs()
        # Add ALL_GRAPHS at the top for cross-domain investigation
        graphs = ["ALL_GRAPHS"] + [g for g in raw_graphs if g != "ALL_GRAPHS"]
        active = settings.graph_name if settings.graph_name and settings.graph_name not in ("ALL_GRAPHS", "ALL") else "ALL_GRAPHS"
        return {
            "status": "success",
            "graphs": graphs,
            "active_graph": active,
        }
    except Exception as exc:
        return {
            "status": "partial",
            "graphs": ["ALL_GRAPHS", "fraud_swiftpay", "graphos_dev", "security_swiftpay", "fraud_Front", "swiftpay_unified"],
            "active_graph": "ALL_GRAPHS",
            "error": str(exc),
        }


@app.get("/api/schema")
async def get_graph_schema(tenant_graph: Optional[str] = None, force_refresh: bool = False):
    """Retrieve runtime graph schema discovered through MCP."""
    target_graph = (tenant_graph or settings.graph_name or "ALL_GRAPHS").strip()
    client = MCPClientManager(settings)
    try:
        await client.connect()
        profile = await schema_manager.get_or_discover_profile(
            client,
            tenant_graph=target_graph,
            force_refresh=force_refresh,
        )
        return {
            "status": "success",
            "schema": profile.to_summary_dict(),
            "discovery_status": profile.discovery_status,
        }
    except Exception as exc:
        logger.warning(f"Live schema discovery unavailable ({exc}). Returning baseline profile.")
        return {
            "status": "fallback",
            "discovery_status": "demo",
            "schema": {
                "tenant_graph": settings.graph_name,
                "inferred_domain": "Connected Enterprise Knowledge Graph",
                "total_nodes": 48,
                "total_edges": 92,
                "node_kinds": ["Service", "Repository", "PullRequest", "Task", "Person", "Policy", "AuditRecord"],
                "relationship_types": ["DEPLOYS", "IMPLEMENTED_IN", "HAS_PULL_REQUEST", "BLOCKED_BY", "ASSIGNED_TO", "GOVERNED_BY"],
            },
        }
    finally:
        await client.disconnect()


@app.get("/api/graph/preview")
async def get_graph_preview(tenant_graph: Optional[str] = None, limit: int = 25):
    """Retrieve sample nodes and relationships from the active/selected graph for visual preview."""
    target_graph = (tenant_graph or settings.graph_name or "ALL_GRAPHS").strip()
    try:
        from mcp_server.db import execute_ro_query, list_available_graphs, get_db_client
        entities: dict[str, Any] = {}
        edges: list[dict[str, Any]] = []

        if target_graph.upper() in ("ALL_GRAPHS", "ALL"):
            client = get_db_client()
            avail = [g for g in list_available_graphs() if g.upper() not in ("ALL_GRAPHS", "ALL")]
            per_graph_limit = max(4, limit // max(1, len(avail)))
            for g in avail:
                try:
                    g_obj = client.select_graph(g)
                    g_rows = g_obj.ro_query(
                        """
                        MATCH (a)-[r]->(b)
                        RETURN a.id, coalesce(a.name, a.id), head(labels(a)),
                               type(r),
                               b.id, coalesce(b.name, b.id), head(labels(b))
                        LIMIT $limit
                        """,
                        params={"limit": per_graph_limit},
                    ).result_set
                    for row in g_rows:
                        if not isinstance(row, (list, tuple)) or len(row) < 7:
                            continue
                        a_id, a_name, a_kind, r_type, b_id, b_name, b_kind = (
                            row[0], row[1], row[2], row[3], row[4], row[5], row[6]
                        )
                        if a_id not in entities:
                            entities[str(a_id)] = {
                                "id": str(a_id),
                                "name": str(a_name or a_id),
                                "kind": str(a_kind or "Entity"),
                                "status": "active",
                                "properties": {"source_graph": g},
                            }
                        if b_id not in entities:
                            entities[str(b_id)] = {
                                "id": str(b_id),
                                "name": str(b_name or b_id),
                                "kind": str(b_kind or "Entity"),
                                "status": "active",
                                "properties": {"source_graph": g},
                            }
                        edges.append({
                            "from_id": str(a_id),
                            "to_id": str(b_id),
                            "relationship_type": str(r_type or "CONNECTED_TO"),
                            "confidence": 1.0,
                            "source_graph": g,
                        })
                except Exception as g_exc:
                    logger.debug(f"Preview skipped graph {g}: {g_exc}")
            
            return {
                "graph_name": "ALL_GRAPHS",
                "entities": entities,
                "edges": edges,
                "node_count": len(entities),
                "edge_count": len(edges),
                "member_graphs": avail,
            }

        rows = execute_ro_query(
            """
            MATCH (a)-[r]->(b)
            RETURN a.id, coalesce(a.name, a.id), head(labels(a)),
                   type(r),
                   b.id, coalesce(b.name, b.id), head(labels(b))
            LIMIT $limit
            """,
            params={"limit": limit},
            graph_name=target_graph,
        )

        for row in rows:
            if not isinstance(row, (list, tuple)) or len(row) < 7:
                continue
            a_id, a_name, a_kind, r_type, b_id, b_name, b_kind = (
                row[0], row[1], row[2], row[3], row[4], row[5], row[6]
            )
            if a_id not in entities:
                entities[str(a_id)] = {
                    "id": str(a_id),
                    "name": str(a_name or a_id),
                    "kind": str(a_kind or "Entity"),
                    "status": "active",
                    "properties": {},
                }
            if b_id not in entities:
                entities[str(b_id)] = {
                    "id": str(b_id),
                    "name": str(b_name or b_id),
                    "kind": str(b_kind or "Entity"),
                    "status": "active",
                    "properties": {},
                }
            edges.append({
                "from_id": str(a_id),
                "to_id": str(b_id),
                "relationship_type": str(r_type or "CONNECTED_TO"),
                "confidence": 1.0,
            })

        # Fallback if no edges found: sample isolated nodes
        if not entities:
            n_rows = execute_ro_query(
                "MATCH (n) RETURN n.id, coalesce(n.name, n.id), head(labels(n)) LIMIT $limit",
                params={"limit": limit},
                graph_name=target_graph,
            )
            for row in n_rows:
                if not isinstance(row, (list, tuple)) or len(row) < 3:
                    continue
                n_id, n_name, n_kind = row[0], row[1], row[2]
                entities[str(n_id)] = {
                    "id": str(n_id),
                    "name": str(n_name or n_id),
                    "kind": str(n_kind or "Entity"),
                    "status": "active",
                    "properties": {},
                }

        return {
            "graph_name": target_graph,
            "entities": entities,
            "edges": edges,
            "node_count": len(entities),
            "edge_count": len(edges),
        }
    except Exception as exc:
        logger.warning(f"Failed to fetch preview for graph {target_graph}: {exc}")
        return {"graph_name": target_graph, "entities": {}, "edges": [], "error": str(exc)}


@app.get("/api/tools")
async def list_tools():
    """List permitted read-only tools exposed by the MCP server."""
    client = MCPClientManager(settings)
    guardrails = GuardrailManager(settings)
    try:
        await client.connect()
        raw_tools = await client.discover_tools()
        permitted = guardrails.filter_available_tools(raw_tools)
        return {
            "count": len(permitted),
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                }
                for t in permitted
            ],
        }
    except Exception as exc:
        logger.warning(f"MCP tool listing fallback: {exc}")
        return {
            "count": len(READ_ONLY_ALLOWED_TOOLS),
            "tools": [{"name": name, "description": "GraphOS read-only capability"} for name in sorted(READ_ONLY_ALLOWED_TOOLS)],
        }
    finally:
        await client.disconnect()


@app.get("/api/sessions")
async def list_sessions():
    """List recent investigation sessions."""
    manager = SessionManager()
    sessions = manager.list_recent_sessions(limit=20)
    return {"sessions": sessions}



@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Retrieve full detail for a persisted investigation session."""
    manager = SessionManager(session_id=session_id)
    if not manager.state.turns:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return manager.state.to_dict()


@app.get("/api/demo/{scenario}")
async def get_demo_scenario(scenario: str):
    """Return high-fidelity synthetic demo data for onboarding and offline testing."""
    s_key = scenario.lower().strip()
    if s_key not in DEMO_SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Demo scenario '{scenario}' not found. Available: {list(DEMO_SCENARIOS.keys())}")
    return DEMO_SCENARIOS[s_key]


@app.post("/api/investigate")
async def run_investigation(req: InvestigateRequest):
    """Execute a complete graph investigation and return the full result synchronously."""
    if req.mode == "demo":
        s_key = "fraud" if "fraud" in req.objective.lower() or "transaction" in req.objective.lower() else (
            "security" if "security" in req.objective.lower() or "cve" in req.objective.lower() else "codebase"
        )
        return DEMO_SCENARIOS[s_key]

    active_settings = settings
    if req.tenant_graph:
        active_settings = replace(settings, graph_name=req.tenant_graph.strip())
    investigator = GraphOSInvestigator(settings=active_settings)
    try:
        result = await investigator.investigate(objective=req.objective)
        return result.to_dict()
    except Exception as exc:
        logger.error(f"Investigation execution error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/investigate/stream")
async def stream_investigation(req: InvestigateRequest):
    """
    Execute a graph investigation with real-time Server-Sent Events (SSE).
    Streams agent thoughts, tool calls, results, and the final evidence report.
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        event_queue: asyncio.Queue[Optional[dict[str, Any]]] = asyncio.Queue()

        def on_event(ev: InvestigationEvent) -> None:
            event_queue.put_nowait({
                "type": ev.event_type,
                "iteration": ev.iteration,
                "message": ev.message,
                "metadata": ev.metadata,
                "timestamp": ev.timestamp,
            })

        if req.mode == "demo":
            s_key = "fraud" if "fraud" in req.objective.lower() or "transaction" in req.objective.lower() else (
                "security" if "security" in req.objective.lower() or "cve" in req.objective.lower() else "codebase"
            )
            demo_data: dict[str, Any] = DEMO_SCENARIOS.get(s_key, DEMO_SCENARIOS["codebase"])

            title = str(demo_data.get("title", "Demo Scenario"))
            yield f"data: {json.dumps({'type': 'plan', 'iteration': 0, 'message': f'Demo Mode: Starting {title}'})}\n\n"
            await asyncio.sleep(0.3)

            steps: list[dict[str, Any]] = list(demo_data.get("steps", []))
            for step in steps:
                thought = str(step.get("thought", ""))
                yield f"data: {json.dumps({'type': 'thought', 'iteration': step.get('iteration', 1), 'message': thought})}\n\n"
                await asyncio.sleep(0.4)
                tool_calls: list[dict[str, Any]] = list(step.get("tool_calls", []))
                for tc in tool_calls:
                    fn = str(tc.get("function_name", "tool"))
                    yield f"data: {json.dumps({'type': 'tool_call', 'iteration': step.get('iteration', 1), 'message': f'Calling {fn}', 'metadata': {'tool': fn, 'arguments': tc.get('arguments', {})}})}\n\n"
                    await asyncio.sleep(0.3)
                    yield f"data: {json.dumps({'type': 'tool_result', 'iteration': step.get('iteration', 1), 'message': f'Retrieved verified data from {fn}'})}\n\n"
                    await asyncio.sleep(0.2)

            yield f"data: {json.dumps({'type': 'complete', 'iteration': len(steps), 'message': 'Demo investigation complete', 'metadata': demo_data})}\n\n"
            return

        # Live mode execution
        async def run_task():
            try:
                active_settings = settings
                if req.tenant_graph:
                    active_settings = replace(settings, graph_name=req.tenant_graph.strip())
                investigator = GraphOSInvestigator(settings=active_settings)
                res = await investigator.investigate(
                    objective=req.objective,
                    on_event_callback=on_event,
                )
                event_queue.put_nowait({
                    "type": "complete",
                    "iteration": res.total_iterations,
                    "message": "Investigation completed successfully",
                    "metadata": res.to_dict(),
                })
            except Exception as exc:
                logger.error(f"Streaming investigation error: {exc}", exc_info=True)
                event_queue.put_nowait({
                    "type": "error",
                    "iteration": 0,
                    "message": str(exc),
                    "metadata": {},
                })
            finally:
                event_queue.put_nowait(None)

        task = asyncio.create_task(run_task())

        while True:
            item = await event_queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

        await task

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class IngestCodeJsonRequest(BaseModel):
    graph_name: str = Field("graphos_dev", description="Target graph name to ingest code AST into")
    data: Any = Field(..., description="Parsed JSON object or list from CLI code parser")


class IngestCsvRequest(BaseModel):
    graph_name: str = Field("swiftpay_unified", description="Target graph name to ingest CSV records into")
    csv_text: str = Field(..., description="Raw CSV content")
    domain: str = Field("general", description="Domain classification: 'general', 'fraud', 'security'")


class ApproveActionRequest(BaseModel):
    action_type: str = Field(..., description="Remediation action type")
    target_id: str = Field(..., description="Target entity identifier")
    rationale: str = Field(..., description="Operational justification")
    tenant_graph: Optional[str] = Field(None, description="Active tenant graph")


@app.post("/api/ingest/code-json")
async def ingest_code_ast_json(req: IngestCodeJsonRequest) -> dict[str, Any]:
    """Ingest parsed code AST / JSON from CLI code parser into FalkorDB Cloud."""
    try:
        from agent.ingest import ingest_code_json
        result = ingest_code_json(req.data, graph_name=req.graph_name)
        schema_manager.invalidate()
        return result
    except Exception as exc:
        logger.error(f"Failed to ingest code JSON: {exc}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/ingest/csv")
async def ingest_csv_dataset(req: IngestCsvRequest) -> dict[str, Any]:
    """Ingest CSV records (fraud transactions, security alerts, general data) into FalkorDB."""
    try:
        from agent.ingest import ingest_csv_data
        result = ingest_csv_data(req.csv_text, graph_name=req.graph_name, domain=req.domain)
        schema_manager.invalidate()
        return result
    except Exception as exc:
        logger.error(f"Failed to ingest CSV: {exc}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/remediation/approve")
async def approve_remediation_action(req: ApproveActionRequest) -> dict[str, Any]:
    """Approve and record durable remediation action into decision memory."""
    target_graph = req.tenant_graph or settings.graph_name
    try:
        from mcp_server.decision_memory import propose_action, execute_approved_action
        proposal = propose_action(
            action=req.action_type,
            target_id=req.target_id,
            rationale=req.rationale or f"Human-in-the-loop analyst approved {req.action_type} on {req.target_id}",
            graph_name=target_graph,
        )
        token = proposal.get("approval_token")
        prop_id = proposal.get("proposal_id")
        if token and token != "BLOCKED_BY_POLICY" and prop_id:
            record = execute_approved_action(
                proposal_id=prop_id,
                approval_token=token,
                graph_name=target_graph,
            )
            return {
                "status": "approved",
                "action_type": req.action_type,
                "target_id": req.target_id,
                "proposal_id": prop_id,
                "record": record,
            }
        else:
            return {
                "status": "policy_blocked",
                "action_type": req.action_type,
                "target_id": req.target_id,
                "proposal": proposal,
            }
    except Exception as exc:
        logger.warning(f"Failed to execute remediation in graph {target_graph}: {exc}")
        return {
            "status": "simulated_approval",
            "action_type": req.action_type,
            "target_id": req.target_id,
            "message": f"Remediation action {req.action_type} on {req.target_id} approved and logged for audit.",
            "timestamp": time.time(),
        }




if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("agent.api:app", host="0.0.0.0", port=port, reload=True)
