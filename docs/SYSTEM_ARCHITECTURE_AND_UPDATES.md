# GraphOS: Universal AI Graph Intelligence Platform
## Comprehensive Architecture, Integration, and Updates Specification

---

## 1. Executive Summary

**GraphOS** is a production-ready, autonomous AI graph intelligence agent built on **FalkorDB Cloud** and the **Model Context Protocol (MCP)**. 

Unlike conventional LLM chatbots that retrieve isolated text snippets or generate plausible guesses, GraphOS navigates **connected graph topology**, verifies real multi-hop entity relationships, enforces deterministic governance policies, and maintains persistent decision memory.

```
+-----------------------------------------------------------------------------------+
|                                  NEXT.JS FRONTEND                                 |
|  - Interactive Prompt Composer       - Dynamic Graph Switcher (Multi-Tenant)      |
|  - Import Dataset Modal (Code/CSV)   - Glowing Multi-Hop Graph Explorer           |
|  - Human-in-the-Loop Remediation     - Real-Time SSE Investigation Stream         |
+-----------------------------------------------------------------------------------+
                                          |  HTTP / SSE Stream
                                          v
+-----------------------------------------------------------------------------------+
|                              GRAPHOS AGENT BACKEND                                |
|  - Fast API Server (agent/api.py)    - Autonomous ReAct Engine (agent/engine.py)  |
|  - Ingestion Engine (agent/ingest.py)- Strict Read-Only Guardrails (guardrails.py)|
|  - Session Context (session.py)      - Dynamic Schema Profiler (schema_context.py)|
+-----------------------------------------------------------------------------------+
                                          |  Model Context Protocol (MCP stdio/HTTP)
                                          v
+-----------------------------------------------------------------------------------+
|                                 MCP SERVER CORE                                   |
|  - Graph Discovery & Cypher Tools    - Counterfactual Simulation Engine           |
|  - Policy Governance (policy.py)     - Durable Decision Memory (decision_memory.py)|
+-----------------------------------------------------------------------------------+
                                          |  Redis/Cypher Protocol
                                          v
+-----------------------------------------------------------------------------------+
|                             FALKORDB CLOUD INSTANCE                               |
|  - swiftpay_unified (Multi-Domain)   - fraud_swiftpay (Financial Graph)           |
|  - security_swiftpay (Cloud Infra)   - graphos_dev (Codebase AST & Dependencies)  |
+-----------------------------------------------------------------------------------+
```

---

## 2. Dynamic Multi-Tenant Graph Architecture

### A. Zero Hardcoded Graph Names
The platform has been decoupled from hardcoded database names:
- Default active graph is configured via `GRAPHOS_GRAPH_NAME=swiftpay_unified` in `.env`.
- Every MCP tool and REST API endpoint accepts an optional `tenant_graph` parameter to execute queries against any tenant database dynamically.
- `GET /api/graphs` discovers all available graphs on the connected FalkorDB instance in real time.

### B. Connected Graph Datasets in FalkorDB Cloud
1. **`swiftpay_unified`** (Default): Multi-domain graph connecting Financial Fraud, Cloud Security alerts, and Codebase Repositories (131+ nodes, 186+ edges).
2. **`fraud_swiftpay`**: Financial fraud dataset with transaction velocity clustering, shared hardware device fingerprints, and mule account chains (685 nodes, 1,474 edges).
3. **`security_swiftpay`**: Cloud infrastructure blast-radius graph with CVE vulnerabilities, IAM permissions, and EC2/database hosts (51 nodes, 75 edges).
4. **`graphos_dev`**: Codebase topology graph with repositories, files, classes, functions, and third-party dependencies (80+ nodes, 100+ edges).

---

## 3. Data Ingestion Engine

GraphOS includes a high-performance ingestion subsystem in [`agent/ingest.py`](file:///Users/apple/Documents/graphhacks/agent/ingest.py) exposed via FastAPI endpoints in [`agent/api.py`](file:///Users/apple/Documents/graphhacks/agent/api.py).

### A. CLI Code Parser JSON Ingestion (`POST /api/ingest/code-json`)
Directly ingests the JSON output of CLI-based code parsers into FalkorDB Cloud. It automatically detects and supports three distinct AST representations:

1. **Project Catalog AST Format:**
   ```json
   {
     "repository": "swiftpay-ledger",
     "files": ["src/payment.py", "src/auth.py"],
     "classes": [{"name": "LedgerService", "file": "src/payment.py"}],
     "functions": [{"name": "process_payout", "file": "src/payment.py"}],
     "dependencies": [{"name": "stripe", "version": "5.4.0"}]
   }
   ```
   *Auto-generates:*
   - `(:Repository)-[:CONTAINS]->(:File)`
   - `(:File)-[:DECLARES]->(:Class)`
   - `(:File)-[:DECLARES]->(:Function)`
   - `(:Repository)-[:DEPENDS_ON]->(:Externaldependency)`

2. **Standard Graph Format:**
   ```json
   {
     "nodes": [
       {"id": "pkg/auth.py", "kind": "File", "name": "auth.py"},
       {"id": "func-verify-token", "kind": "Function", "name": "verify_token"}
     ],
     "edges": [
       {"from": "pkg/auth.py", "to": "func-verify-token", "type": "DECLARES"}
     ]
   }
   ```

3. **Entity List Format:**
   ```json
   [
     {"id": "func-verify-jwt", "name": "verify_jwt", "kind": "Function", "calls": ["func-hash-secret"]},
     {"id": "func-hash-secret", "name": "hash_secret", "kind": "Function"}
   ]
   ```

### B. Live CSV Ingestion (`POST /api/ingest/csv`)
Accepts CSV text or uploaded `.csv` files with automatic column detection:
- **Fraud Domain:** Automatically identifies `transaction_id`, `from_account`, `to_account`, `amount`, and `source_ip` to merge `(:Account)`, `(:Transaction)`, and `(:IP)` nodes linked with `[:TRANSFERRED_TO]` and `[:ORIGINATED_FROM]`.
- **Security Domain:** Automatically maps `alert_id`, `cve`, `severity`, `source_ip`, and `hostname` to merge `(:Alert)`, `(:Vulnerability)`, and `(:Host)` nodes linked with `[:AFFECTS]`.
- **General Relational Data:** Dynamically merges entities and links matching foreign key references.

### C. Enterprise DB Connector Architecture (Supabase / Postgres)
A synchronous connector schema is integrated in the UI, enabling mirroring of relational foreign keys into FalkorDB graph topology.

---

## 4. Human-in-the-Loop Decision Governance

GraphOS enforces strict separation between **autonomous read-only investigation** and **durable state modification**:

1. **Read-Only Automated Exploration:**
   - During reasoning, the agent is constrained by [`agent/guardrails.py`](file:///Users/apple/Documents/graphhacks/agent/guardrails.py). Destructive Cypher keywords (`CREATE`, `SET`, `DELETE`, `DROP`, `MERGE`) are strictly blocked.
2. **Policy Verification & Simulation:**
   - When a remediation action is considered (e.g., `QUARANTINE_NODE`, `FREEZE_ACCOUNT`, `BLOCK_IP`), [`mcp_server/policy.py`](file:///Users/apple/Documents/graphhacks/mcp_server/policy.py) checks organizational policies.
   - [`mcp_server/counterfactual.py`](file:///Users/apple/Documents/graphhacks/mcp_server/counterfactual.py) performs a dry-run simulation of the blast radius and reversible impact.
3. **Formal Proposal & Authorization:**
   - [`mcp_server/decision_memory.py`](file:///Users/apple/Documents/graphhacks/mcp_server/decision_memory.py) creates an `ActionProposal` in the graph with status `APPROVED_PENDING_EXECUTION` and issues a unique `approval_token`.
4. **Human Execution:**
   - The user reviews the recommendation in the Next.js workspace and clicks **"Approve Remediation"**.
   - `POST /api/remediation/approve` executes the change, updates the entity state to `'quarantined'`, and writes an immutable `AuditRecord` node into FalkorDB.

---

## 5. Next.js Frontend Architecture & Aesthetics

The frontend in `frontend/` is built with **Next.js 16 (Turbopack)**, **React 19**, and **Tailwind CSS**:

1. **Interactive Prompt Composer & Celestial Arch Hero:**
   - Luminous dark/celestial hero section with animated starfield overlay and atmospheric arch curve.
   - Frosted glass prompt composer with voice speech recognition fallback.
2. **Import Dataset Modal ([`ImportDatasetModal.tsx`](file:///Users/apple/Documents/graphhacks/frontend/src/components/ImportDatasetModal.tsx)):**
   - 3 interactive tabs: **Code Parser JSON**, **Live CSV**, and **Database Connector**.
   - Accessible directly from the Landing Page header and from the Workspace top bar.
3. **Interactive Graph Explorer ([`GraphExplorer.tsx`](file:///Users/apple/Documents/graphhacks/frontend/src/components/GraphExplorer.tsx)):**
   - Canvas-based physics graph with node color palette:
     * **Red/Rose:** `Vulnerability`, `Incident`, `Alert`
     * **Violet/Purple:** `Account`, `Transaction`, `Payment`
     * **Blue/Sky:** `Service`, `Host`, `IP`, `File`
     * **Emerald/Green:** `Person`, `Team`
     * **Amber/Gold:** `Policy`, `AuditRecord`
   - Active path illumination and directed relationship arrows.
4. **Workspace Mode Toggle:**
   - **Live MCP Mode:** Connects to the active FalkorDB instance over SSE stream.
   - **Demo Scenarios Mode:** Fallback for offline demonstrations.

---

## 6. Verification and Test Results

| Test / Capability | Target Module | Verified Result |
| :--- | :--- | :--- |
| **CLI Code Parser Ingestion** | `agent/ingest.py` | ✅ Passed: Successfully ingested project catalog (6 nodes, 5 edges) and entity lists into FalkorDB Cloud. |
| **Live CSV Ingestion** | `agent/ingest.py` | ✅ Passed: Successfully parsed and linked fraud transactions and IP addresses (6 nodes, 4 edges). |
| **Dynamic Graph Enumeration** | `agent/api.py` | ✅ Passed: Discovers `swiftpay_unified`, `fraud_swiftpay`, `security_swiftpay`, `graphos_dev`. |
| **Human Remediation Approval** | `mcp_server/decision_memory.py` | ✅ Passed: Executed `QUARANTINE_NODE` on entity `P-2120`; node status set to `'quarantined'`, `AuditRecord` created. |
| **Grounding Negative Control** | `agent/engine.py` | ✅ Passed: Evaluated isolated `AuditRecord` nodes in `graphos_dev`; agent reported 0 relationships without hallucinating. |
| **Frontend Production Build** | `frontend/` (Next.js 16) | ✅ Passed: `npm run build` compiled in 425ms with 0 TypeScript/Turbopack errors. |
| **Python Static Compilation** | `agent/*.py`, `mcp_server/*.py` | ✅ Passed: `py_compile` passed on all Python files with exit code 0. |

---

## 7. Operations & Quickstart

### Prerequisites
- Python 3.11+ with `.venv` active
- Node.js 18+ and `npm`

### Starting the Platform
```bash
# 1. Start the Backend API (Port 8000)
source .venv/bin/activate
uvicorn agent.api:app --reload --port 8000

# 2. In a separate terminal, start the Next.js Frontend (Port 3000)
cd frontend
npm run dev
```

### Accessing the Platform
- Web Application: `http://localhost:3000`
- API Swagger Documentation: `http://localhost:8000/docs`
- API Health Check: `http://localhost:8000/api/health`

---

## 6. Federated All Graphs Engine Resolution

### Issue Addressed
The user identified that selecting `"All Graphs"` was previously defaulting to `swiftpay_unified` due to hardcoded fallbacks across `.env`, `Workspace.tsx`, and `mcp_server/config.py`.

### Solutions Implemented & Verified
1. **Dynamic Fan-out Across All 5 Graphs**:
   - `search_connected_entities`, `run_read_only_cypher_query`, `search_entities_advanced`, `get_entity_profile`, `inspect_entity_neighbors`, and `traverse_relationships` execute read operations across all 5 FalkorDB graphs simultaneously:
     * `fraud_swiftpay` (690 nodes, 1,476 edges)
     * `graphos_dev` (97 nodes, 113 edges)
     * `security_swiftpay` (51 nodes, 75 edges)
     * `fraud_Front` (115 nodes, 167 edges)
     * `swiftpay_unified` (983 nodes, 2,054 edges)
2. **Provenance & Source Graph Attribution**:
   - Every discovered entity and relationship carries an explicit `source_graph` tag (`"source_graph": "graphos_dev"`, `"source_graph": "fraud_swiftpay"`, etc.), allowing the agent to cite exact data origins in its final findings.
3. **Label-Agnostic Querying**:
   - Removed rigid `(n:Entity)` label assumptions in graph algorithms and intelligence tools (`mcp_server/intelligence.py`), allowing seamless matches on non-`Entity` labeled graphs like `security_swiftpay` (`:Host`, `:Vulnerability`, `:Alert`) and `fraud_Front`.
4. **UI Dropdown & Default Selection**:
   - Updated `.env`, `agent/config.py`, `agent/api.py`, `page.tsx`, and `Workspace.tsx` so `ALL_GRAPHS` is the default active target and is preserved without being inadvertently overwritten by `swiftpay_unified`.
   - Workspace header explicitly indicates: `🌐 Federated Multi-Graph Engine (All 5 Datasets Active)`.
