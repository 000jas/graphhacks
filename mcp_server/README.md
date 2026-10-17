# GraphOS MCP Server — Advanced Feature Expansion

GraphOS is an enterprise-grade, evidence-bound **Model Context Protocol (MCP) Server** providing deep graph intelligence, structural reasoning, counterfactual planning, and organizational memory over cloud-hosted **FalkorDB**.

---

## 🌟 The 6 Core Investigative Questions

GraphOS empowers AI agents to answer:
1. **What is connected?** (Multi-hop relationship traversal, alternative paths, and subgraph extraction)
2. **What evidence supports that connection?** (Edge provenance, verification rates, source records, and freshness)
3. **What is unusual or important?** (PageRank, Betweenness Centrality, Hopcroft-Tarjan cut vertices, and anomaly detection)
4. **What could happen next?** (Deterministic blast radius, consequence trees, fallback connection analysis, and isolated components)
5. **Which actions are permitted?** (Zero-trust policy enforcement and counterfactual candidate action comparison)
6. **How can every conclusion be independently verified?** (Durable organizational memory, traceable finding records, and cryptographically auditable proposals)

---

## 🛠️ Complete 37 Composable Tools Catalog

### 1. Advanced Graph Intelligence
- **`discover_relationship_patterns(entity_id, max_depth=3, min_frequency=1)`**: Discovers recurring multi-hop relationship patterns, indirect connections, and triangular motifs.
- **`find_common_neighbors(entity_ids, direction="both", limit=25)`**: Identifies shared dependencies, teams, resources, or services with Jaccard similarity and Adamic-Adar specificity weighting.
- **`find_alternative_paths(source_id, target_id, max_depth=6, max_paths=5)`**: Discovers multiple independent paths between entities, evaluating path redundancy and intermediate node-disjoint independence.
- **`detect_critical_dependencies(scope_kind="", top_k=10)`**: Detects articulation points (cut vertices) using Hopcroft-Tarjan DFS and single points of failure.
- **`detect_communities(max_iterations=20, min_community_size=2)`**: Identifies tightly-coupled clusters using asynchronous Label Propagation and highlights inter-community bridge edges.
- **`detect_graph_anomalies(anomaly_types=None)`**: Flags isolated/orphaned nodes, potential duplicate entities, extreme degree spikes, and unverified relationships.
- **`analyze_reachability(start_entity_id, target_entity_ids, direction="downstream", max_depth=5)`**: Bounded reachability exploration under direction, depth, relationship, and target-kind constraints.
- **`compare_connectivity(source_a_id, source_b_id, target_id="")`**: Compares topological positioning, shared vs unique neighbors, and proximity differences between two entities.
- **`run_graph_algorithm(algorithm, entity_kinds, top_k)`**: Computes PageRank, Degree Centrality, Betweenness Centrality (Brandes), Closeness Centrality, Cycle Detection, Connected Components, or Community Detection.

### 2. Intelligent Investigation Tools
- **`search_entities_advanced(query, kinds, statuses, property_filters, connected_to, limit=20, offset=0)`**: Multi-filter entity search with pagination (`total_count`, `offset`, `has_more`).
- **`search_connected_entities(query, limit=10, kind="")`**: Fast text search over entity names and identifiers.
- **`get_entity_profile(entity_id)`**: 360° entity properties, labels, incoming & outgoing relationships with evidence.
- **`traverse_relationships(entity_id, relationship_types, depth=2, limit=20)`**: Multi-hop relationship traversal with path nodes and edge evidence.
- **`find_shortest_evidence_path(source_id, target_id, max_depth=8)`**: Shortest verifiable connection chain.
- **`compare_entities(entity_ids, include_relationships=True)`**: Side-by-side attribute, dependency, and relationship comparison for 2–6 entities.
- **`investigate_entity_cluster(entity_ids, max_depth=2)`**: Bounded exploration of multiple entities, discovering internal links, shared intermediaries, and aggregated risks.
- **`extract_investigation_subgraph(focal_entity_ids, max_depth=2, max_nodes=50)`**: Compact, self-contained JSON subgraph for inspection and reasoning.
- **`compare_evidence_paths(source_id, target_id, candidate_paths_limit=4)`**: Ranks candidate explanation chains by hop distance, cumulative confidence, and verification rate.
- **`batch_get_entities(entity_ids)`**: Efficient batch retrieval of up to 50 entities in a single round-trip.
- **`generate_investigation_summary(investigation_title, entity_ids)`**: Synthesizes verified facts, derived connections, data gaps, and recommended next steps.

### 3. Schema Discovery & Adaptive Graph Reasoning
- **`discover_graph_schema(sample_size=100, refresh_cache=False)`**: Safely inspects entity kinds, relationship directionality matrices, property catalogs with inferred data types, graph density, and schema anomalies across any domain without a rigid ontology.

### 4. Evidence Quality, Provenance, & Temporal Reasoning
- **`evaluate_evidence_quality(entity_id="", max_depth=2, stale_days_threshold=30)`**: Computes verification rates, confidence distribution, evidence freshness, and unverified edge samples.
- **`detect_conflicting_evidence(scope_entity_ids=None)`**: Identifies contradictory statuses, unavailable assignees on active tasks, or policy-violating dependencies.
- **`inspect_temporal_graph(entity_id, as_of_timestamp=None)`**: Chronological timeline of observed events, distinguishing current from historical or superseded links.
- **`retrieve_source_documents(entity_ids, limit=20)`**: Retrieves linked specifications, tickets, and compliance records.

### 5. Graph-Guided Impact & Risk Analysis
- **`analyze_graph_impact(root_entity_id, direction="downstream", max_depth=4)`**: Multi-hop blast radius scoring, consequence trees, and critical asset impact.
- **`assess_change_risk_and_impact(proposed_change_type, target_entity_id)`**: Deep change impact analysis including fallback connection analysis, isolated component simulation, and prerequisite verification.

### 6. Counterfactual Planning & Action Evaluation
- **`simulate_action(action, target_id, params)`**: Non-destructive Counterfactual Graph Planning evaluating state diffs, policy checks, and mitigations.
- **`evaluate_candidate_actions(candidate_actions, target_entity_id)`**: Side-by-side comparison of multiple candidate interventions, generating rank-ordered recommendations with explicit rejection reasons.
- **`check_policy(action, target_id, params)`**: Zero-trust deterministic policy enforcement (`PERMITTED`, `REJECTED`, `UNRESOLVED`).

### 7. Safe Universal Cypher Querying
- **`run_read_only_cypher_query(query, params=None, limit=50)`**: Executes safe, validated read-only Cypher queries against the connected graph while strictly rejecting any data-mutating or administrative keywords (`CREATE`, `MERGE`, `SET`, `DELETE`, `REMOVE`, `DROP`, `ALTER`, `CALL dbms`).

### 8. Persistent Organizational & Decision Memory
- **`propose_action(action, target_id, rationale, evidence_ids, params)`**: Formally proposes an action bound to evidence with cryptographic approval tokens.
- **`execute_approved_action(proposal_id, approval_token)`**: Token-verified, idempotent state mutation with permanent audit logging.
- **`record_outcome(finding_id, target_entity_ids, summary, outcome_status)`**: Durable organizational memory linking outcomes back to graph entities.
- **`query_decision_memory(query="", entity_id="", status="", limit=20)`**: Search historical proposals, executions, and decision records.
- **`record_investigation_finding(title, objective, key_findings, supporting_entity_ids)`**: Persists investigation conclusions as connected `InvestigationFinding` entities.
- **`supersede_finding(finding_id, reason, superseding_finding_id="")`**: Updates findings challenged by newer evidence while preserving full audit history.

---

## 🚀 Running the Server & Verification

### Configuration (`.env`)
```env
FALKORDB_HOST=r-6jissuruar.instance-27k50cn68.hc-7up0crkyn.ap-south-1.aws.f2e0a955bb84.cloud
FALKORDB_PORT=54637
FALKORDB_USERNAME=falkordb
FALKORDB_PASSWORD=aOuxFFj8vO6A
FALKORDB_SSL=false
GRAPHOS_GRAPH_NAME=graphos_dev
```

### Running the Server
```bash
python server.py
```

### Running the Test Suites
```bash
# Verify original 12 tools (100% backwards compatibility)
python test_server.py

# Verify all 36 tools across all 11 requirements sections
python test_expanded_server.py
```
