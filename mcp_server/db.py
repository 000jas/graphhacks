from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Optional

from falkordb import FalkorDB
from falkordb.graph import Graph

from config import settings

logger = logging.getLogger("graphos.mcp.db")


class GraphError(Exception):
    """Base exception for GraphOS database operations."""


class GraphNotFoundError(GraphError):
    """Raised when a specified graph or tenant does not exist."""


class QueryExecutionError(GraphError):
    """Raised when a Cypher query fails execution."""


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
        logger.info(f"Connected to FalkorDB Cloud at {settings.host}:{settings.port} (ssl={settings.ssl})")
        return client
    except Exception as exc:
        if settings.ssl:
            logger.warning(
                f"SSL connection to {settings.host}:{settings.port} failed ({exc}). Retrying with plaintext RESP..."
            )
            kwargs["ssl"] = False
            try:
                fallback_client = FalkorDB(**kwargs)
                fallback_client.connection.ping()
                logger.info("Fallback connection established to FalkorDB Cloud (ssl=False)")
                return fallback_client
            except Exception as fallback_exc:
                raise GraphError(
                    f"Failed to connect to FalkorDB Cloud: {type(fallback_exc).__name__}"
                ) from fallback_exc
        raise GraphError(f"Failed to connect to FalkorDB Cloud: {type(exc).__name__}") from exc


def get_graph(graph_name: Optional[str] = None) -> Graph:
    """Retrieve a validated FalkorDB graph instance."""
    safe_name = settings.validate_graph_name(graph_name)
    client = get_db_client()
    return client.select_graph(safe_name)


def execute_ro_query(
    query: str,
    params: Optional[dict[str, Any]] = None,
    graph_name: Optional[str] = None,
) -> list[Any]:
    """Execute a read-only Cypher query with sanitized error handling."""
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
    """Return summary statistics for the active graph."""
    safe_name = settings.validate_graph_name(graph_name)
    nodes = execute_ro_query("MATCH (n:Entity) RETURN count(n) AS c", graph_name=safe_name)
    edges = execute_ro_query("MATCH ()-[r]->() RETURN count(r) AS c", graph_name=safe_name)
    kinds = execute_ro_query("MATCH (n:Entity) RETURN DISTINCT n.kind ORDER BY n.kind", graph_name=safe_name)
    rel_types = execute_ro_query("MATCH ()-[r]->() RETURN DISTINCT type(r) ORDER BY type(r)", graph_name=safe_name)

    return {
        "graph_name": safe_name,
        "total_entities": nodes[0][0] if nodes else 0,
        "total_relationships": edges[0][0] if edges else 0,
        "entity_kinds": [k[0] for k in kinds if k[0]],
        "relationship_types": [r[0] for r in rel_types if r[0]],
    }
