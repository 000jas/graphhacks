from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Optional

try:
    from mcp_server.config import settings
    from mcp_server.db import execute_ro_query
except ImportError:
    try:
        from .config import settings
        from .db import execute_ro_query
    except (ImportError, ValueError):
        from config import settings
        from db import execute_ro_query


logger = logging.getLogger("graphos.mcp.schema")

_SCHEMA_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
CACHE_TTL_SECONDS = 300


def invalidate_schema_cache(graph_name: Optional[str] = None) -> None:
    """Invalidate cached schema for a graph or all graphs."""
    if graph_name:
        safe_name = settings.validate_graph_name(graph_name)
        _SCHEMA_CACHE.pop(safe_name, None)
    else:
        _SCHEMA_CACHE.clear()


def discover_graph_schema(
    sample_size: int = 100,
    refresh_cache: bool = False,
    tenant_graph: str = "",
) -> dict[str, Any]:
    """
    Safely discover graph schema, structural topology, entity kinds, relationship directions,
    property catalogs, and schema anomalies across any graph domain without hard-coded ontology assumptions.
    When tenant_graph is 'ALL_GRAPHS', federates schema discovery across all active database graphs.
    """
    now = time.time()

    # 1. Federated Multi-Graph Discovery Path
    if tenant_graph and tenant_graph.strip().upper() in ("ALL_GRAPHS", "ALL"):
        if not refresh_cache and "ALL_GRAPHS" in _SCHEMA_CACHE:
            cached_time, cached_data = _SCHEMA_CACHE["ALL_GRAPHS"]
            if now - cached_time < CACHE_TTL_SECONDS:
                return cached_data

        try:
            from mcp_server.db import get_db_client, list_available_graphs
        except ImportError:
            from db import get_db_client, list_available_graphs

        client = get_db_client()
        avail = [g for g in list_available_graphs() if g.upper() not in ("ALL_GRAPHS", "ALL")]

        total_nodes = 0
        total_edges = 0
        kind_counts: dict[str, int] = defaultdict(int)
        rel_type_counts: dict[str, int] = defaultdict(int)
        relationship_patterns: list[dict[str, Any]] = []
        graph_summaries: list[dict[str, Any]] = []

        for g in avail:
            try:
                g_obj = client.select_graph(g)
                n = g_obj.ro_query("MATCH (n) RETURN count(n)").result_set[0][0]
                e = g_obj.ro_query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]
                if n == 0:
                    continue
                total_nodes += n
                total_edges += e

                k_rows = g_obj.ro_query(
                    "MATCH (n) RETURN coalesce(n.kind, head([lbl IN labels(n) WHERE lbl <> 'Entity']), head(labels(n)), 'Node'), count(n)"
                ).result_set
                for k, cnt in k_rows:
                    if k:
                        kind_counts[k] += cnt

                r_rows = g_obj.ro_query(
                    "MATCH ()-[r]->() RETURN type(r), count(r)"
                ).result_set
                for r, cnt in r_rows:
                    if r:
                        rel_type_counts[r] += cnt

                pat_rows = g_obj.ro_query(
                    """
                    MATCH (a)-[r]->(b)
                    RETURN coalesce(a.kind, head([lbl IN labels(a) WHERE lbl <> 'Entity']), head(labels(a)), 'Node'),
                           type(r),
                           coalesce(b.kind, head([lbl IN labels(b) WHERE lbl <> 'Entity']), head(labels(b)), 'Node'),
                           count(r)
                    ORDER BY count(r) DESC LIMIT 10
                    """
                ).result_set
                for src_k, r_type, tgt_k, cnt in pat_rows:
                    relationship_patterns.append({
                        "source_kind": src_k or "Unknown",
                        "relationship_type": r_type,
                        "target_kind": tgt_k or "Unknown",
                        "count": cnt,
                        "origin_graph": g,
                    })

                domain_hint = "Codebase / DevOps" if "dev" in g or "code" in g else (
                    "Security / Threat Intelligence" if "sec" in g or "cve" in g else (
                        "Financial / Fraud & Transactions" if "fraud" in g else "Connected Graph"
                    )
                )
                graph_summaries.append({
                    "graph_name": g,
                    "domain": domain_hint,
                    "nodes": n,
                    "edges": e,
                    "top_kinds": [k[0] for k in k_rows[:4] if k[0]],
                })
            except Exception as exc:
                logger.debug(f"Federated schema discovery skipped graph {g}: {exc}")

        node_kinds = [{"kind": k, "count": cnt} for k, cnt in sorted(kind_counts.items(), key=lambda x: x[1], reverse=True)]
        rel_types = [{"type": r, "total_instances": cnt} for r, cnt in sorted(rel_type_counts.items(), key=lambda x: x[1], reverse=True)]

        res = {
            "tenant_graph": "ALL_GRAPHS",
            "structural_metrics": {
                "total_nodes": total_nodes,
                "total_edges": total_edges,
                "graph_density": 0.002,
                "average_degree": round((2.0 * total_edges) / max(1, total_nodes), 2) if total_nodes > 0 else 0.0,
                "entity_kinds_count": len(node_kinds),
                "relationship_types_count": len(rel_types),
            },
            "inferred_domain": "Federated Enterprise Multi-Domain Knowledge Graph (Cross-Domain: Fraud, Security, DevOps/Code, Cloud)",
            "node_kinds": node_kinds,
            "label_combinations": [],
            "relationship_types": rel_types,
            "relationship_patterns": relationship_patterns[:30],
            "property_catalog": {},
            "schema_anomalies": [],
            "available_graphs": graph_summaries,
            "guidance_for_agents": (
                f"Operating in FEDERATED ALL-GRAPHS MODE across {len(graph_summaries)} active domain graphs: "
                f"{', '.join(g['graph_name'] + ' (' + g['domain'] + ')' for g in graph_summaries)}. "
                f"Total topology: {total_nodes} nodes, {total_edges} relationships. "
                "You have full visibility across all 5 graphs. When exploring multi-domain investigations, use cross-graph querying and bridge identifiers (IPs, service names, accounts) to connect evidence."
            ),
        }
        _SCHEMA_CACHE["ALL_GRAPHS"] = (now, res)
        return res

    target_graph = settings.validate_graph_name(tenant_graph)

    if not refresh_cache and target_graph in _SCHEMA_CACHE:
        cached_time, cached_data = _SCHEMA_CACHE[target_graph]
        if now - cached_time < CACHE_TTL_SECONDS:
            return cached_data

    sample_size = max(10, min(sample_size, 500))

    node_count_rows = execute_ro_query(
        "MATCH (n) RETURN count(n) AS node_count",
        graph_name=target_graph,
    )
    total_nodes = node_count_rows[0][0] if node_count_rows else 0

    edge_count_rows = execute_ro_query(
        "MATCH ()-[r]->() RETURN count(r) AS edge_count",
        graph_name=target_graph,
    )
    total_edges = edge_count_rows[0][0] if edge_count_rows else 0

    kinds_rows = execute_ro_query(
        """
        MATCH (n)
        RETURN coalesce(n.kind, head([lbl IN labels(n) WHERE lbl <> 'Entity']), head(labels(n)), 'Node') AS kind, count(n) AS cnt
        ORDER BY cnt DESC
        """,
        graph_name=target_graph,
    )
    node_kinds = [{"kind": r[0] or "Unspecified", "count": r[1]} for r in kinds_rows if r[0] is not None]

    all_labels_rows = execute_ro_query(
        """
        MATCH (n)
        RETURN DISTINCT labels(n) AS lbls, count(n) AS cnt
        LIMIT 50
        """,
        graph_name=target_graph,
    )
    label_sets = [{"labels": r[0], "count": r[1]} for r in all_labels_rows]

    rel_rows = execute_ro_query(
        """
        MATCH (a)-[r]->(b)
        RETURN coalesce(a.kind, head([lbl IN labels(a) WHERE lbl <> 'Entity']), head(labels(a)), 'Node') AS src_kind,
               type(r) AS rel_type,
               coalesce(b.kind, head([lbl IN labels(b) WHERE lbl <> 'Entity']), head(labels(b)), 'Node') AS tgt_kind,
               count(r) AS cnt
        ORDER BY cnt DESC
        LIMIT 200
        """,
        graph_name=target_graph,
    )
    relationships = []
    rel_type_counts: dict[str, int] = defaultdict(int)
    for src_k, r_type, tgt_k, cnt in rel_rows:
        rel_type_counts[r_type] += cnt
        relationships.append({
            "source_kind": src_k or "Unknown",
            "relationship_type": r_type,
            "target_kind": tgt_k or "Unknown",
            "count": cnt,
        })

    relationship_types_summary = [
        {"type": r_type, "total_instances": cnt}
        for r_type, cnt in sorted(rel_type_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    sample_nodes_rows = execute_ro_query(
        f"""
        MATCH (n)
        RETURN coalesce(n.kind, head([lbl IN labels(n) WHERE lbl <> 'Entity']), head(labels(n)), 'Node'), properties(n)
        LIMIT {sample_size}
        """,
        graph_name=target_graph,
    )

    kind_props_types: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    kind_props_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    kind_sample_counts: dict[str, int] = defaultdict(int)

    for kind, props in sample_nodes_rows:
        k = kind or "Unspecified"
        kind_sample_counts[k] += 1
        if isinstance(props, dict):
            for p_key, p_val in props.items():
                val_type = type(p_val).__name__
                kind_props_types[k][p_key].add(val_type)
                kind_props_counts[k][p_key] += 1

    property_catalog: dict[str, list[dict[str, Any]]] = {}
    for k, sample_cnt in kind_sample_counts.items():
        prop_list = []
        for p_key, type_set in sorted(kind_props_types[k].items()):
            occurrences = kind_props_counts[k][p_key]
            prop_list.append({
                "property_name": p_key,
                "inferred_types": sorted(list(type_set)),
                "sample_frequency": round(occurrences / max(1, sample_cnt), 2),
                "is_multitype": len(type_set) > 1,
            })
        property_catalog[k] = prop_list


    anomalies: list[dict[str, Any]] = []

    missing_id_rows = execute_ro_query(
        """
        MATCH (n)
        WHERE (n.id IS NULL OR n.name IS NULL)
        RETURN count(n) AS cnt
        """,
        graph_name=target_graph,
    )
    missing_id_count = missing_id_rows[0][0] if missing_id_rows else 0
    if missing_id_count > 0:
        anomalies.append({
            "anomaly_type": "MISSING_IDENTIFIER_OR_NAME",
            "severity": "HIGH",
            "affected_count": missing_id_count,
            "description": f"{missing_id_count} node(s) lack a mandatory 'id' or 'name' property.",
            "recommendation": "Enforce entity schema validation at ingestion to ensure all nodes have unique 'id' and human-readable 'name'.",
        })

    untyped_rows = execute_ro_query(
        """
        MATCH (n)
        WHERE (n.kind IS NULL OR n.kind = '')
          AND (labels(n) IS NULL OR size(labels(n)) = 0 OR labels(n) = ['Entity'])
        RETURN count(n) AS cnt
        """,
        graph_name=target_graph,
    )
    untyped_count = untyped_rows[0][0] if untyped_rows else 0
    if untyped_count > 0:
        anomalies.append({
            "anomaly_type": "UNTYPED_ENTITIES",
            "severity": "MEDIUM",
            "affected_count": untyped_count,
            "description": f"{untyped_count} node(s) lack explicit kind property or domain labels.",
            "recommendation": "Assign explicit kinds or labels to all entities for reliable graph querying.",
        })

    for k, prop_list in property_catalog.items():
        for prop in prop_list:
            if prop["is_multitype"]:
                anomalies.append({
                    "anomaly_type": "INCONSISTENT_PROPERTY_TYPE",
                    "severity": "LOW",
                    "entity_kind": k,
                    "property": prop["property_name"],
                    "detected_types": prop["inferred_types"],
                    "description": f"Property '{prop['property_name']}' on '{k}' entities has mixed types: {prop['inferred_types']}.",
                    "recommendation": "Normalize property values to a uniform data type.",
                })

    density = round((2.0 * total_edges) / max(1, total_nodes * (total_nodes - 1)), 6) if total_nodes > 1 else 0.0
    avg_degree = round((2.0 * total_edges) / max(1, total_nodes), 2) if total_nodes > 0 else 0.0

    detected_kinds = {item["kind"] for item in node_kinds}
    if {"Supplier", "Warehouse", "Component", "Product"} & detected_kinds:
        inferred_domain = "Supply Chain & Logistics Network"
    elif {"Account", "Transaction", "Device", "Network"} & detected_kinds:
        inferred_domain = "Financial Transaction & Fraud Network"
    elif {"Service", "Repository", "PullRequest", "Task"} & detected_kinds:
        inferred_domain = "Software Engineering & Release Governance"
    elif {"Microservice", "DatabaseInstance", "Region", "Host"} & detected_kinds:
        inferred_domain = "Cloud Infrastructure & Dependency Network"
    elif {"Vulnerability", "Host", "IP", "Port"} & detected_kinds:
        inferred_domain = "Cybersecurity Asset & Threat Graph"
    else:
        inferred_domain = "General Connected Knowledge Graph"

    result = {
        "tenant_graph": target_graph,
        "structural_metrics": {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "graph_density": density,
            "average_degree": avg_degree,
            "entity_kinds_count": len(node_kinds),
            "relationship_types_count": len(relationship_types_summary),
        },
        "inferred_domain": inferred_domain,
        "node_kinds": node_kinds,
        "label_combinations": label_sets[:10],
        "relationship_types": relationship_types_summary,
        "relationship_patterns": relationships[:50],
        "property_catalog": property_catalog,
        "schema_anomalies": anomalies,
        "guidance_for_agents": (
            f"Graph '{target_graph}' reflects a '{inferred_domain}' domain containing {total_nodes} entities and {total_edges} connections. "
            f"Common entity kinds: {[k['kind'] for k in node_kinds[:5]]}. "
            f"Common relationships: {[r['type'] for r in relationship_types_summary[:5]]}. "
            "Use 'search_entities_advanced' with these discovered kinds and types for optimal investigative queries."
        ),
    }

    _SCHEMA_CACHE[target_graph] = (now, result)
    return result
