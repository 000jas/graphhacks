from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Optional

from falkordb import FalkorDB
from falkordb.graph import Graph

try:
    from mcp_server.config import settings
except ImportError:
    from config import settings  # type: ignore[import-not-found,no-redef]

logger = logging.getLogger("graphos.mcp.db")


class GraphError(Exception):
    """Base exception for GraphOS database operations."""


class GraphNotFoundError(GraphError):
    """Raised when a specified graph or tenant does not exist."""


class QueryExecutionError(GraphError):
    """Raised when a Cypher query fails execution."""


SYSTEM_GRAPHS: set[str] = {
    "graphos_auth",
    "graphos_history",
    "graphos_system",
    "graphos_internal",
    "graphos_memory",
}


def is_system_graph(graph_name: Optional[str]) -> bool:
    """Return True if graph_name is a reserved internal system graph."""
    if not graph_name:
        return False
    clean = graph_name.strip().lower()
    if clean in SYSTEM_GRAPHS:
        return True
    if clean.startswith("graphos_auth") or clean.startswith("graphos_history"):
        return True
    return False


@lru_cache(maxsize=1)
def get_db_client() -> FalkorDB:
    """Initialize and cache the FalkorDB Cloud client with resilient connection logic."""
    kwargs: dict[str, Any] = {
        "host": settings.host,
        "port": settings.port,
        "ssl": settings.ssl,
        "socket_timeout": 10,
        "socket_connect_timeout": 10,
    }
    if settings.username:
        kwargs["username"] = settings.username
    if settings.password:
        kwargs["password"] = settings.password

    try:
        client = FalkorDB(**kwargs)
        client.connection.ping()
        logger.debug(f"Connected to FalkorDB Cloud at {settings.host}:{settings.port} (ssl={kwargs['ssl']})")
        return client
    except Exception as exc:
        opposite_ssl = not kwargs["ssl"]
        logger.warning(
            f"FalkorDB connection with ssl={kwargs['ssl']} to {settings.host}:{settings.port} failed ({exc}). Retrying with ssl={opposite_ssl}..."
        )
        kwargs["ssl"] = opposite_ssl
        try:
            fallback_client = FalkorDB(**kwargs)
            fallback_client.connection.ping()
            logger.debug(f"Fallback connection established to FalkorDB Cloud (ssl={opposite_ssl})")
            return fallback_client
        except Exception as fallback_exc:
            raise GraphError(
                f"Failed to connect to FalkorDB Cloud at {settings.host}:{settings.port}: {type(fallback_exc).__name__} ({fallback_exc})"
            ) from fallback_exc


class FederatedQueryResult:
    """Wrapper matching FalkorDB QueryResult interface for federated responses."""
    def __init__(self, result_set: list[Any]) -> None:
        self.result_set = result_set


class FederatedGraph:
    """
    Virtual federated graph spanning all physical graph databases present in FalkorDB Cloud.
    Transparently distributes read-only Cypher queries across all domains (fraud, security, code, etc.).
    """
    def __init__(self, client: FalkorDB) -> None:
        self.client = client
        self.name = "ALL_GRAPHS"

    def ro_query(self, query: str, params: Optional[dict[str, Any]] = None, timeout: Optional[int] = None) -> FederatedQueryResult:
        rows = execute_ro_query(query, params=params, graph_name="ALL_GRAPHS")
        return FederatedQueryResult(rows)

    def query(self, query: str, params: Optional[dict[str, Any]] = None, timeout: Optional[int] = None) -> Any:
        # State mutations default to primary unified graph
        safe_fallback = "swiftpay_unified" if "swiftpay_unified" in list_available_graphs() else settings.default_graph
        return self.client.select_graph(safe_fallback).query(query, params=params, timeout=timeout)


def get_graph(graph_name: Optional[str] = None) -> Any:
    """Retrieve a validated FalkorDB graph instance or virtual FederatedGraph."""
    safe_name = settings.validate_graph_name(graph_name)
    if safe_name.strip().upper() in ("ALL_GRAPHS", "ALL"):
        client = get_db_client()
        return FederatedGraph(client)
    client = get_db_client()
    return client.select_graph(safe_name)


def execute_ro_query(
    query: str,
    params: Optional[dict[str, Any]] = None,
    graph_name: Optional[str] = None,
) -> list[Any]:
    """
    Execute a read-only Cypher query with sanitized error handling.
    When graph_name is 'ALL_GRAPHS' (or default), queries all domain graphs in parallel/sequence
    and returns aggregated, unified results across all available datasets.
    """
    effective_name = settings.validate_graph_name(graph_name)
    if effective_name.strip().upper() in ("ALL_GRAPHS", "ALL"):
        client = get_db_client()
        avail = list_available_graphs()
        target_graphs = [g for g in avail if g.upper() not in ("ALL_GRAPHS", "ALL", "FRAUD_DEMO") and not is_system_graph(g)]

        # 1. Pure count aggregation (e.g., MATCH (n) RETURN count(n) AS node_count)
        q_norm = query.strip().upper().replace(" ", "").replace("\n", "")
        if "RETURNCOUNT(" in q_norm and "GROUPBY" not in q_norm and "COLLECT(" not in q_norm:
            total_sum = 0
            for g in target_graphs:
                try:
                    res = client.select_graph(g).ro_query(query, params=params)
                    if res.result_set and isinstance(res.result_set[0][0], (int, float)):
                        total_sum += int(res.result_set[0][0])
                except Exception as exc:
                    logger.debug(f"Federated count on graph '{g}' skipped: {exc}")
            return [[total_sum]]

        # 2. General Cypher query: fan out across all target graphs
        combined_rows: list[Any] = []
        seen_keys: set[str] = set()

        for g in target_graphs:
            try:
                res = client.select_graph(g).ro_query(query, params=params)
                for row in res.result_set:
                    # Deduplicate identical entity rows
                    key = str(row[:4]) if isinstance(row, (list, tuple)) and len(row) >= 4 else str(row)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        combined_rows.append(row)
            except Exception as exc:
                logger.debug(f"Federated query on graph '{g}' skipped: {exc}")

        return combined_rows

    graph = get_graph(graph_name)
    try:
        result = graph.ro_query(query, params=params)
        return result.result_set
    except Exception as exc:
        clean_msg = str(exc).split("errCtx:")[0].strip() if "errCtx:" in str(exc) else str(exc)
        logger.error(f"Read-only query failed: {clean_msg}")
        raise QueryExecutionError(f"Query execution failed: {clean_msg}") from exc


def execute_rw_query(
    query: str,
    params: Optional[dict[str, Any]] = None,
    graph_name: Optional[str] = None,
) -> list[Any]:
    """Execute a mutating/write Cypher query with sanitized error handling."""
    graph = get_graph(graph_name)
    try:
        result = graph.query(query, params=params)
        return result.result_set
    except Exception as exc:
        clean_msg = str(exc).split("errCtx:")[0].strip() if "errCtx:" in str(exc) else str(exc)
        logger.error(f"Write query failed: {clean_msg}")
        raise QueryExecutionError(f"State mutation failed: {clean_msg}") from exc


def get_graph_stats(graph_name: Optional[str] = None) -> dict[str, Any]:
    """Return summary statistics for the active graph or all federated graphs."""
    if graph_name and graph_name.strip().upper() in ("ALL_GRAPHS", "ALL"):
        client = get_db_client()
        avail = [g for g in list_available_graphs() if g.upper() not in ("ALL_GRAPHS", "ALL") and not is_system_graph(g)]
        total_nodes = 0
        total_edges = 0
        kinds_set: set[str] = set()
        rels_set: set[str] = set()

        for g in avail:
            try:
                g_obj = client.select_graph(g)
                n = g_obj.ro_query("MATCH (n) RETURN count(n)").result_set[0][0]
                e = g_obj.ro_query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]
                total_nodes += n
                total_edges += e
                k_rows = g_obj.ro_query("MATCH (n) RETURN DISTINCT coalesce(n.kind, head([lbl IN labels(n) WHERE lbl <> 'Entity']), head(labels(n)), 'Node')").result_set
                for r in k_rows:
                    if r[0]:
                        kinds_set.add(r[0])
                r_rows = g_obj.ro_query("MATCH ()-[r]->() RETURN DISTINCT type(r)").result_set
                for r in r_rows:
                    if r[0]:
                        rels_set.add(r[0])
            except Exception:
                pass

        return {
            "graph_name": "ALL_GRAPHS",
            "total_entities": total_nodes,
            "total_relationships": total_edges,
            "entity_kinds": sorted(kinds_set),
            "relationship_types": sorted(rels_set),
            "member_graphs": avail,
        }

    safe_name = settings.validate_graph_name(graph_name)
    nodes = execute_ro_query("MATCH (n) RETURN count(n) AS c", graph_name=safe_name)
    edges = execute_ro_query("MATCH ()-[r]->() RETURN count(r) AS c", graph_name=safe_name)
    kinds = execute_ro_query(
        """
        MATCH (n)
        RETURN DISTINCT coalesce(n.kind, head([lbl IN labels(n) WHERE lbl <> 'Entity']), head(labels(n)), 'Node') AS k
        ORDER BY k
        """,
        graph_name=safe_name,
    )
    rel_types = execute_ro_query("MATCH ()-[r]->() RETURN DISTINCT type(r) ORDER BY type(r)", graph_name=safe_name)

    return {
        "graph_name": safe_name,
        "total_entities": nodes[0][0] if nodes else 0,
        "total_relationships": edges[0][0] if edges else 0,
        "entity_kinds": [k[0] for k in kinds if k[0]],
        "relationship_types": [r[0] for r in rel_types if r[0]],
    }


def list_available_graphs() -> list[str]:
    """Retrieve all available graph names from the FalkorDB instance dynamically, excluding internal system graphs."""
    client = get_db_client()
    try:
        raw = client.connection.execute_command("GRAPH.LIST")
        graphs = [g.decode("utf-8") if isinstance(g, bytes) else str(g) for g in raw]
        return [g for g in graphs if not is_system_graph(g)]
    except Exception as exc:
        logger.warning(f"Failed to list graphs: {exc}")
        safe_default = settings.default_graph if not is_system_graph(settings.default_graph) else "swiftpay_unified"
        return [safe_default]


