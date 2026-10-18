"""FalkorDB Ingestion engine for GraphAgent code graph JSON output."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import find_dotenv, load_dotenv

logger = logging.getLogger("graphagent.ingester")


def _sanitize_ident(ident: str, default: str = "Entity") -> str:
    """Sanitize Cypher label or relationship type to alphanumeric characters."""
    clean = "".join(c for c in ident if c.isalnum() or c == "_")
    return clean if clean else default


def get_falkordb_connection(
    host: Optional[str] = None,
    port: Optional[int] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    ssl: Optional[bool] = None,
) -> Any:
    """Initialize a FalkorDB connection using parameters or discovered .env."""
    try:
        from falkordb import FalkorDB
    except ImportError:
        raise RuntimeError(
            "The 'falkordb' library is required to save graphs to FalkorDB. "
            "Please install it using: pip install falkordb"
        )

    # Load environment variables if not already set
    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path)

    f_host = host or os.getenv("FALKORDB_HOST", "localhost")
    f_port_str = port or os.getenv("FALKORDB_PORT", "6379")
    try:
        f_port = int(f_port_str)
    except ValueError:
        f_port = 6379

    f_user = username or os.getenv("FALKORDB_USERNAME", None)
    f_pass = password or os.getenv("FALKORDB_PASSWORD", None)
    f_ssl_str = os.getenv("FALKORDB_SSL", "false").lower() if ssl is None else str(ssl).lower()
    f_ssl = f_ssl_str in ("true", "1", "yes")

    conn_kwargs: Dict[str, Any] = {
        "host": f_host,
        "port": f_port,
        "ssl": f_ssl,
        "socket_timeout": 15,
        "socket_connect_timeout": 15,
    }
    if f_user:
        conn_kwargs["username"] = f_user
    if f_pass:
        conn_kwargs["password"] = f_pass

    try:
        client = FalkorDB(**conn_kwargs)
        client.connection.ping()
        logger.debug(f"Connected to FalkorDB at {f_host}:{f_port} (ssl={f_ssl})")
        return client, f_host, f_port
    except Exception as exc:
        if f_ssl:
            logger.warning(f"SSL connection failed ({exc}). Retrying without SSL...")
            conn_kwargs["ssl"] = False
            try:
                fallback_client = FalkorDB(**conn_kwargs)
                fallback_client.connection.ping()
                logger.debug(f"Connected to FalkorDB at {f_host}:{f_port} (ssl=False)")
                return fallback_client, f_host, f_port
            except Exception as e2:
                raise ConnectionError(f"Failed to connect to FalkorDB at {f_host}:{f_port}: {e2}") from e2
        raise ConnectionError(f"Failed to connect to FalkorDB at {f_host}:{f_port}: {exc}") from exc


def resolve_json_file(file_path: Optional[str] = None) -> Path:
    """Find the output JSON file from argument or standard locations."""
    if file_path:
        p = Path(file_path).resolve()
        if p.is_file():
            return p
        raise FileNotFoundError(f"Specified graph JSON file does not exist: {file_path}")

    # Search common candidate locations
    candidates = [
        Path("output.json"),
        Path(".graphagent/graph_data.json"),
        Path("agent/codeparser/output.json"),
        Path("agent/codeparser/.graphagent/graph_data.json"),
        Path("codeparser/output.json"),
        Path("codeparser/.graphagent/graph_data.json"),
        Path("tests/sample_repo/.graphagent/graph_data.json"),
        Path("agent/codeparser/tests/sample_repo/.graphagent/graph_data.json"),
    ]

    for c in candidates:
        resolved = c.resolve()
        if resolved.is_file():
            return resolved

    raise FileNotFoundError(
        "Could not find output JSON file. Looked for: 'output.json' and '.graphagent/graph_data.json'. "
        "Run the parser first: python run.py . (or specify the path with --file path/to/file.json)"
    )


def ingest_graph_json(
    json_path: Path,
    graph_name: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    ssl: Optional[bool] = None,
    clear_existing: bool = False,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Ingest a parsed graph JSON file into FalkorDB."""
    start_time = time.perf_counter()

    # 1. Parse JSON
    with open(json_path, "r", encoding="utf-8") as f:
        graph_data = json.load(f)

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    repo_meta = graph_data.get("repository", {})
    repo_name = repo_meta.get("name", "repository")

    # 2. Determine target graph name
    target_graph = (
        graph_name
        or os.getenv("CODE_GRAPH_NAME")
        or os.getenv("FALKORDB_GRAPH")
        or os.getenv("GRAPHOS_GRAPH_NAME")
        or "graphos_dev"
    )
    if target_graph.upper() in ("ALL_GRAPHS", "ALL"):
        target_graph = os.getenv("CODE_GRAPH_NAME", "graphos_dev")

    # 3. Connect to FalkorDB
    client, connected_host, connected_port = get_falkordb_connection(
        host=host, port=port, username=username, password=password, ssl=ssl
    )
    graph = client.select_graph(target_graph)

    if clear_existing:
        if verbose:
            print(f"🗑️ Clearing existing entities in graph '{target_graph}'...")
        try:
            graph.query("MATCH (n) DETACH DELETE n")
        except Exception as e:
            logger.warning(f"Could not clear graph: {e}")

    # 4. Create indices for performance
    try:
        graph.query("CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.id)")
        graph.query("CREATE INDEX IF NOT EXISTS FOR (f:File) ON (f.id)")
    except Exception:
        pass

    # 5. Group nodes by type/label and batch ingest
    nodes_by_label: Dict[str, List[Dict[str, Any]]] = {}
    file_ids: List[str] = []

    for n in nodes:
        raw_type = n.get("type", "entity").strip()
        label = _sanitize_ident(raw_type.capitalize(), default="Entity")
        nid = n.get("id")
        if not nid:
            continue

        if label == "File":
            file_ids.append(nid)

        props = {
            "id": nid,
            "name": n.get("name") or nid,
            "kind": label,
            "type": raw_type,
            "file_path": n.get("file_path", ""),
            "start_line": n.get("start_line", 0),
            "end_line": n.get("end_line", 0),
            "language": n.get("language", ""),
            "docstring": n.get("docstring", ""),
            "return_type": n.get("return_type", ""),
            "source_ref": f"code:{n.get('file_path', '')}:{nid}",
        }
        if "parameters" in n:
            props["parameters"] = json.dumps(n["parameters"]) if isinstance(n["parameters"], list) else str(n["parameters"])

        extra_props = n.get("properties", {})
        if isinstance(extra_props, dict):
            for k, v in extra_props.items():
                if isinstance(v, (str, int, float, bool)):
                    props[k] = v

        nodes_by_label.setdefault(label, []).append(props)

    ingested_nodes = 0
    BATCH_SIZE = 250

    for label, batch_list in nodes_by_label.items():
        for i in range(0, len(batch_list), BATCH_SIZE):
            chunk = batch_list[i : i + BATCH_SIZE]
            cypher = f"""
            UNWIND $batch AS item
            MERGE (n:{label} {{id: item.id}})
            SET n:Entity,
                n.name = item.name,
                n.kind = item.kind,
                n.type = item.type,
                n.file_path = item.file_path,
                n.start_line = item.start_line,
                n.end_line = item.end_line,
                n.language = item.language,
                n.docstring = item.docstring,
                n.return_type = item.return_type,
                n.source_ref = item.source_ref
            """
            graph.query(cypher, params={"batch": chunk})
            ingested_nodes += len(chunk)

    # 6. Group edges by type and batch ingest
    edges_by_type: Dict[str, List[Dict[str, Any]]] = {}
    for e in edges:
        raw_type = e.get("type", "CONNECTED_TO").strip()
        rel_type = _sanitize_ident(raw_type.upper(), default="CONNECTED_TO")
        src = e.get("source")
        tgt = e.get("target")
        if not src or not tgt:
            continue

        edge_record = {
            "source": src,
            "target": tgt,
            "resolution": e.get("resolution", "resolved"),
            "line": e.get("line", 0),
            "confidence": float(e.get("confidence", 1.0)),
        }
        edges_by_type.setdefault(rel_type, []).append(edge_record)

    ingested_edges = 0
    for rel_type, batch_list in edges_by_type.items():
        for i in range(0, len(batch_list), BATCH_SIZE):
            chunk = batch_list[i : i + BATCH_SIZE]
            cypher = f"""
            UNWIND $batch AS edge
            MERGE (src:Entity {{id: edge.source}})
            MERGE (tgt:Entity {{id: edge.target}})
            MERGE (src)-[r:{rel_type}]->(tgt)
            SET r.resolution = edge.resolution,
                r.line = edge.line,
                r.confidence = edge.confidence
            """
            graph.query(cypher, params={"batch": chunk})
            ingested_edges += len(chunk)

    # 7. Connect Repository Node if available
    try:
        repo_id = f"repo-{_sanitize_ident(repo_name.lower())}"
        graph.query(
            """
            MERGE (repo:Repository {id: $repo_id})
            SET repo:Entity,
                repo.name = $repo_name,
                repo.kind = 'Repository',
                repo.last_ingested_at = $ts
            """,
            params={
                "repo_id": repo_id,
                "repo_name": repo_name,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        )
        if file_ids:
            graph.query(
                """
                UNWIND $fids AS fid
                MATCH (repo:Repository {id: $repo_id})
                MATCH (f:File {id: fid})
                MERGE (repo)-[:CONTAINS]->(f)
                """,
                params={"repo_id": repo_id, "fids": file_ids[:100]},
            )
    except Exception as exc:
        logger.debug(f"Optional repository node link skipped: {exc}")

    elapsed = time.perf_counter() - start_time

    return {
        "status": "success",
        "file": str(json_path),
        "target_graph": target_graph,
        "host": f"{connected_host}:{connected_port}",
        "nodes_ingested": ingested_nodes,
        "edges_ingested": ingested_edges,
        "labels": list(nodes_by_label.keys()),
        "relationship_types": list(edges_by_type.keys()),
        "elapsed_seconds": elapsed,
    }


def print_ingestion_summary(result: Dict[str, Any]) -> None:
    """Format and print ingestion report."""
    print("\n" + "=" * 65)
    print("                    FALKORDB INGESTION SUMMARY")
    print("=" * 65)
    print(f"  • Status:               SUCCESS ✅")
    print(f"  • Graph JSON File:      {result['file']}")
    print(f"  • Target FalkorDB Graph: {result['target_graph']}")
    print(f"  • Connected Host:       {result['host']}")
    print(f"  • Execution Time:       {result['elapsed_seconds']:.2f} seconds")
    print(f"  • Ingested Nodes:       {result['nodes_ingested']} (labels: {', '.join(result['labels'])})")
    print(f"  • Ingested Edges:       {result['edges_ingested']} (types: {', '.join(result['relationship_types'])})")
    print("=" * 65 + "\n")
