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
    """
    target_graph = settings.validate_graph_name(tenant_graph)
    now = time.time()

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
