# GraphOS MCP Server — Standalone Package

This directory contains the standalone, cloud-connected **GraphOS Model Context Protocol (MCP) Server** for FalkorDB.

## Features & Capabilities

- **12 Composable Tools**:
  1. `search_connected_entities`: Partial text, ID, and kind-filtered entity discovery.
  2. `get_entity_profile`: 360° entity properties, provenance, incoming & outgoing relationships.
  3. `traverse_relationships`: Directed multi-hop path traversal with edge evidence.
  4. `find_shortest_evidence_path`: Shortest verifiable connection chain.
  5. `run_graph_algorithm`: PageRank, Degree Centrality, Cycle Detection, Connected Components.
  6. `analyze_graph_impact`: Blast radius scoring, consequence tree, critical dependency chains.
  7. `retrieve_source_documents`: Source specifications and compliance documents.
  8. `check_policy`: Deterministic zero-trust policy engine (`PERMITTED`, `REJECTED`, `UNRESOLVED`).
  9. `simulate_action`: Counterfactual Graph Planning (non-destructive state diffs & risk analysis).
  10. `propose_action`: Formally propose actions bound to evidence with cryptographic approval tokens.
  11. `execute_approved_action`: Token-verified, idempotent execution with graph audit logging.
  12. `record_outcome`: Durable organizational memory linking outcomes back to graph entities.

## Configuration

Credentials and settings are loaded from `.env`:

```env
FALKORDB_HOST=r-6jissuruar.instance-27k50cn68.hc-7up0crkyn.ap-south-1.aws.f2e0a955bb84.cloud
FALKORDB_PORT=54637
FALKORDB_USERNAME=falkordb
FALKORDB_PASSWORD=aOuxFFj8vO6A
FALKORDB_SSL=false
GRAPHOS_GRAPH_NAME=graphos_dev
```

## Running the Server

Run directly with Python:
```bash
python server.py
```

Run test suite:
```bash
python test_server.py
```
