from __future__ import annotations

import csv
import io
import json
import logging
import re
from typing import Any, Optional

from mcp_server.config import settings, validate_identifier
from mcp_server.db import execute_rw_query, execute_ro_query

logger = logging.getLogger("graphos.agent.ingest")


def clean_rel_type(rel_name: str) -> str:
    """Normalize relationship string to uppercase alphanumeric/underscore."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", rel_name.strip()).upper()
    return cleaned if cleaned else "CONNECTED_TO"


def clean_label(label: str) -> str:
    """Normalize label string to PascalCase alphanumeric."""
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", label.strip())
    return cleaned if cleaned else "Entity"


def ingest_code_json(data: dict[str, Any] | list[Any], graph_name: str) -> dict[str, Any]:
    """
    Ingest parsed code AST / JSON output from a CLI parser into FalkorDB.
    Supports standard graph format ({nodes: [], edges: []}) and project catalog format.
    """
    target_graph = settings.validate_graph_name(graph_name)
    nodes_created = 0
    edges_created = 0

    # Format 1: Standard Graph Dict with nodes and edges/relationships
    if isinstance(data, dict) and ("nodes" in data or "entities" in data):
        raw_nodes = data.get("nodes") or data.get("entities") or []
        raw_edges = data.get("edges") or data.get("relationships") or data.get("links") or []

        # 1. Ingest Nodes
        for n in raw_nodes:
            if not isinstance(n, dict):
                continue
            nid = str(n.get("id") or n.get("key") or n.get("name") or "").strip()
            if not nid:
                continue
            label = clean_label(n.get("kind") or n.get("label") or n.get("type") or "CodeEntity")
            name = str(n.get("name") or nid).strip()
            props = {k: v for k, v in n.items() if k not in ("id", "kind", "label", "type") and not isinstance(v, (dict, list))}
            props["name"] = name
            props["id"] = nid

            cypher = f"""
            MERGE (n:{label} {{id: $id}})
            SET n += $props
            """
            try:
                execute_rw_query(cypher, params={"id": nid, "props": props}, graph_name=target_graph)
                nodes_created += 1
            except Exception as e:
                logger.warning(f"Failed to merge node {nid}: {e}")

        # 2. Ingest Edges
        for e in raw_edges:
            if not isinstance(e, dict):
                continue
            from_id = str(e.get("from") or e.get("source") or e.get("source_id") or "").strip()
            to_id = str(e.get("to") or e.get("target") or e.get("target_id") or "").strip()
            if not from_id or not to_id:
                continue
            rel_type = clean_rel_type(str(e.get("type") or e.get("relationship") or e.get("rel") or "DEPENDS_ON"))
            e_props = {k: v for k, v in e.items() if k not in ("from", "to", "source", "target", "source_id", "target_id", "type", "relationship", "rel") and not isinstance(v, (dict, list))}

            cypher = f"""
            MATCH (a {{id: $from_id}})
            MATCH (b {{id: $to_id}})
            MERGE (a)-[r:{rel_type}]->(b)
            SET r += $props
            """
            try:
                execute_rw_query(cypher, params={"from_id": from_id, "to_id": to_id, "props": e_props}, graph_name=target_graph)
                edges_created += 1
            except Exception as exc:
                logger.warning(f"Failed to merge edge {from_id} -> {to_id}: {exc}")

        return {
            "status": "success",
            "graph_name": target_graph,
            "format": "nodes_edges_graph",
            "nodes_ingested": nodes_created,
            "edges_ingested": edges_created,
        }

    # Format 2: Project Catalog ({ "repository": "...", "files": [...], "functions": [...], "dependencies": [...] })
    if isinstance(data, dict):
        repo_name = str(data.get("repository") or data.get("project") or data.get("name") or "code-project").strip()
        repo_id = f"repo-{repo_name}"
        
        # Merge Repository node
        execute_rw_query(
            "MERGE (r:Repository {id: $id}) SET r.name = $name",
            params={"id": repo_id, "name": repo_name},
            graph_name=target_graph,
        )
        nodes_created += 1

        # Files
        files = data.get("files") or []
        for f in files:
            f_path = str(f if isinstance(f, str) else (f.get("path") or f.get("name") or "")).strip()
            if not f_path:

                continue
            f_id = f"file-{repo_name}-{f_path}"
            execute_rw_query(
                """
                MERGE (f:File {id: $id}) SET f.path = $path, f.name = $path
                WITH f
                MATCH (r:Repository {id: $repo_id})
                MERGE (r)-[:CONTAINS]->(f)
                """,
                params={"id": f_id, "path": f_path, "repo_id": repo_id},
                graph_name=target_graph,
            )
            nodes_created += 1
            edges_created += 1

        # Functions
        funcs = data.get("functions") or []
        for fn in funcs:
            fn_name = str(fn if isinstance(fn, str) else (fn.get("name") or fn.get("id") or "")).strip()
            if not fn_name:

                continue
            fn_file = str(fn.get("file") or fn.get("path") or "").strip() if isinstance(fn, dict) else ""
            fn_id = f"func-{repo_name}-{fn_name}"

            execute_rw_query(
                "MERGE (fn:Function {id: $id}) SET fn.name = $name",
                params={"id": fn_id, "name": fn_name},
                graph_name=target_graph,
            )
            nodes_created += 1

            if fn_file:
                file_id = f"file-{repo_name}-{fn_file}"
                execute_rw_query(
                    """
                    MATCH (f:File {id: $f_id}), (fn:Function {id: $fn_id})
                    MERGE (f)-[:DECLARES]->(fn)
                    """,
                    params={"f_id": file_id, "fn_id": fn_id},
                    graph_name=target_graph,
                )
                edges_created += 1
            else:
                execute_rw_query(
                    """
                    MATCH (r:Repository {id: $repo_id}), (fn:Function {id: $fn_id})
                    MERGE (r)-[:CONTAINS]->(fn)
                    """,
                    params={"repo_id": repo_id, "fn_id": fn_id},
                    graph_name=target_graph,
                )
                edges_created += 1

        # Classes
        classes = data.get("classes") or []
        for cls in classes:
            cls_name = str(cls if isinstance(cls, str) else (cls.get("name") or cls.get("id") or "")).strip()
            if not cls_name:
                continue
            cls_file = str(cls.get("file") or cls.get("path") or "").strip() if isinstance(cls, dict) else ""
            cls_id = f"class-{repo_name}-{cls_name}"

            execute_rw_query(
                "MERGE (c:Class {id: $id}) SET c.name = $name",
                params={"id": cls_id, "name": cls_name},
                graph_name=target_graph,
            )
            nodes_created += 1

            if cls_file:
                file_id = f"file-{repo_name}-{cls_file}"
                execute_rw_query(
                    """
                    MATCH (f:File {id: $f_id}), (c:Class {id: $cls_id})
                    MERGE (f)-[:DECLARES]->(c)
                    """,
                    params={"f_id": file_id, "cls_id": cls_id},
                    graph_name=target_graph,
                )
                edges_created += 1

        # Dependencies
        deps = data.get("dependencies") or data.get("packages") or []
        for d in deps:
            d_name = str(d if isinstance(d, str) else (d.get("name") or d.get("id") or "")).strip()
            d_ver = str(d.get("version") or "latest") if isinstance(d, dict) else "latest"
            if not d_name:
                continue
            d_id = f"dep-{d_name}"
            execute_rw_query(
                """
                MERGE (d:Externaldependency {id: $id}) SET d.name = $name, d.version = $ver
                WITH d
                MATCH (r:Repository {id: $repo_id})
                MERGE (r)-[:DEPENDS_ON]->(d)
                """,
                params={"id": d_id, "name": d_name, "ver": d_ver, "repo_id": repo_id},
                graph_name=target_graph,
            )
            nodes_created += 1
            edges_created += 1

        return {
            "status": "success",
            "graph_name": target_graph,
            "format": "project_catalog",
            "repository": repo_name,
            "nodes_ingested": nodes_created,
            "edges_ingested": edges_created,
        }

    # Format 3: Raw List of Entities
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            nid = str(item.get("id") or item.get("name") or item.get("path") or "").strip()
            if not nid:
                continue
            label = clean_label(item.get("kind") or item.get("label") or item.get("type") or "CodeEntity")
            name = str(item.get("name") or nid).strip()
            props = {k: v for k, v in item.items() if k not in ("id", "kind", "label", "type") and not isinstance(v, (dict, list))}
            props["name"] = name
            props["id"] = nid

            execute_rw_query(
                f"MERGE (n:{label} {{id: $id}}) SET n += $props",
                params={"id": nid, "props": props},
                graph_name=target_graph,
            )
            nodes_created += 1

            # Check calls or imports
            calls = item.get("calls") or []
            for target_call in calls:
                target_id = str(target_call if isinstance(target_call, str) else target_call.get("id", "")).strip()
                if target_id:
                    try:
                        execute_rw_query(
                            """
                            MATCH (a {id: $from_id})
                            MERGE (b:Function {id: $to_id})
                            MERGE (a)-[:CALLS]->(b)
                            """,
                            params={"from_id": nid, "to_id": target_id},
                            graph_name=target_graph,
                        )
                        edges_created += 1
                    except Exception:
                        pass

        return {
            "status": "success",
            "graph_name": target_graph,
            "format": "entity_list",
            "nodes_ingested": nodes_created,
            "edges_ingested": edges_created,
        }

    raise ValueError("Unrecognized code JSON parser format. Please provide {nodes: [], edges: []}, a project catalog, or an entity list.")


def ingest_csv_data(csv_text: str, graph_name: str, domain: str = "general") -> dict[str, Any]:
    """
    Ingest CSV text rows into FalkorDB as graph nodes and relationships.
    Auto-detects Fraud, Security, and General relational columns.
    """
    target_graph = settings.validate_graph_name(graph_name)
    stream = io.StringIO(csv_text.strip())
    reader = csv.DictReader(stream)
    rows = list(reader)

    if not rows:
        raise ValueError("CSV is empty or missing headers")

    headers = [h.strip() for h in (reader.fieldnames or []) if h]
    nodes_created = 0
    edges_created = 0

    lower_headers = {h.lower(): h for h in headers}

    # 1. Fraud Domain Detection
    is_fraud = domain == "fraud" or any(k in lower_headers for k in ("account_id", "from_account", "mule", "transaction_id", "sender_id"))
    # 2. Security Domain Detection
    is_security = domain == "security" or any(k in lower_headers for k in ("alert_id", "cve", "vulnerability", "source_ip", "hostname"))

    for row in rows:
        r_clean = {k.strip(): str(v).strip() for k, v in row.items() if k and v is not None and str(v).strip()}

        if is_fraud:
            # Transaction
            tx_id = r_clean.get(lower_headers.get("transaction_id", "")) or r_clean.get(lower_headers.get("tx_id", "")) or r_clean.get(lower_headers.get("id", ""))
            sender = r_clean.get(lower_headers.get("from_account", "")) or r_clean.get(lower_headers.get("account_id", "")) or r_clean.get(lower_headers.get("sender", ""))
            receiver = r_clean.get(lower_headers.get("to_account", "")) or r_clean.get(lower_headers.get("target_account", "")) or r_clean.get(lower_headers.get("receiver", ""))
            ip = r_clean.get(lower_headers.get("ip_address", "")) or r_clean.get(lower_headers.get("ip", "")) or r_clean.get(lower_headers.get("source_ip", ""))
            amount = r_clean.get(lower_headers.get("amount", ""))

            if sender:
                execute_rw_query("MERGE (a:Account {id: $id})", params={"id": sender}, graph_name=target_graph)
                nodes_created += 1
            if receiver:
                execute_rw_query("MERGE (b:Account {id: $id})", params={"id": receiver}, graph_name=target_graph)
                nodes_created += 1
            if ip:
                execute_rw_query("MERGE (i:Ip {id: $id})", params={"id": ip}, graph_name=target_graph)
                nodes_created += 1
                if sender:
                    execute_rw_query(
                        "MATCH (a:Account {id: $aid}), (i:Ip {id: $ipid}) MERGE (a)-[:LOGGED_IN_FROM]->(i)",
                        params={"aid": sender, "ipid": ip},
                        graph_name=target_graph,
                    )
                    edges_created += 1

            if tx_id:
                execute_rw_query(
                    "MERGE (t:Transaction {id: $id}) SET t += $props",
                    params={"id": tx_id, "props": r_clean},
                    graph_name=target_graph,
                )
                nodes_created += 1
                if sender:
                    execute_rw_query("MATCH (a:Account {id: $aid}), (t:Transaction {id: $tid}) MERGE (a)-[:SENT]->(t)", params={"aid": sender, "tid": tx_id}, graph_name=target_graph)
                    edges_created += 1
                if receiver:
                    execute_rw_query("MATCH (t:Transaction {id: $tid}), (b:Account {id: $bid}) MERGE (t)-[:RECEIVED_BY]->(b)", params={"tid": tx_id, "bid": receiver}, graph_name=target_graph)
                    edges_created += 1
            elif sender and receiver:
                execute_rw_query(
                    "MATCH (a:Account {id: $aid}), (b:Account {id: $bid}) MERGE (a)-[r:SENT_MONEY_TO]->(b) SET r += $props",
                    params={"aid": sender, "bid": receiver, "props": r_clean},
                    graph_name=target_graph,
                )
                edges_created += 1

        elif is_security:
            # Security Alert / Incident
            alert_id = r_clean.get(lower_headers.get("alert_id", "")) or r_clean.get(lower_headers.get("id", ""))
            ip = r_clean.get(lower_headers.get("source_ip", "")) or r_clean.get(lower_headers.get("ip", ""))
            host = r_clean.get(lower_headers.get("host", "")) or r_clean.get(lower_headers.get("hostname", ""))
            svc = r_clean.get(lower_headers.get("service", "")) or r_clean.get(lower_headers.get("service_name", ""))
            cve = r_clean.get(lower_headers.get("cve", "")) or r_clean.get(lower_headers.get("vulnerability", ""))

            if alert_id:
                execute_rw_query("MERGE (al:Securityalert {id: $id}) SET al += $props", params={"id": alert_id, "props": r_clean}, graph_name=target_graph)
                nodes_created += 1
            if ip:
                execute_rw_query("MERGE (i:Ip {id: $id})", params={"id": ip}, graph_name=target_graph)
                nodes_created += 1
                if alert_id:
                    execute_rw_query("MATCH (al:Securityalert {id: $aid}), (i:Ip {id: $ipid}) MERGE (al)-[:OBSERVED_SOURCE_IP]->(i)", params={"aid": alert_id, "ipid": ip}, graph_name=target_graph)
                    edges_created += 1
            if host:
                execute_rw_query("MERGE (h:Host {id: $id})", params={"id": host}, graph_name=target_graph)
                nodes_created += 1
                if alert_id:
                    execute_rw_query("MATCH (al:Securityalert {id: $aid}), (h:Host {id: $hid}) MERGE (al)-[:TARGETS]->(h)", params={"aid": alert_id, "hid": host}, graph_name=target_graph)
                    edges_created += 1
            if svc:
                execute_rw_query("MERGE (s:Service {id: $id})", params={"id": svc}, graph_name=target_graph)
                nodes_created += 1
                if host:
                    execute_rw_query("MATCH (s:Service {id: $sid}), (h:Host {id: $hid}) MERGE (s)-[:RUNS_ON]->(h)", params={"sid": svc, "hid": host}, graph_name=target_graph)
                    edges_created += 1
            if cve:
                execute_rw_query("MERGE (v:Vulnerability {id: $id})", params={"id": cve}, graph_name=target_graph)
                nodes_created += 1
                if svc:
                    execute_rw_query("MATCH (s:Service {id: $sid}), (v:Vulnerability {id: $vid}) MERGE (s)-[:HAS_VULNERABILITY]->(v)", params={"sid": svc, "vid": cve}, graph_name=target_graph)
                    edges_created += 1

        else:
            # General Domain Ingestion
            # Primary column is first column
            primary_col = headers[0]
            primary_id = r_clean.get(primary_col)
            if not primary_id:
                continue
            primary_label = clean_label(primary_col.replace("_id", "").replace("id", "")) or "Entity"

            execute_rw_query(
                f"MERGE (n:{primary_label} {{id: $id}}) SET n += $props",
                params={"id": primary_id, "props": r_clean},
                graph_name=target_graph,
            )
            nodes_created += 1

            # Check if any other header is an ID/foreign key
            for col in headers[1:]:
                if col.lower().endswith("_id") or col.lower().endswith("id"):
                    val = r_clean.get(col)
                    if val and val != primary_id:
                        sec_label = clean_label(col.replace("_id", "").replace("id", "")) or "Entity"
                        execute_rw_query(f"MERGE (b:{sec_label} {{id: $id}})", params={"id": val}, graph_name=target_graph)
                        rel_name = clean_rel_type(f"LINKS_{col}")
                        execute_rw_query(
                            f"MATCH (a:{primary_label} {{id: $aid}}), (b:{sec_label} {{id: $bid}}) MERGE (a)-[:{rel_name}]->(b)",
                            params={"aid": primary_id, "bid": val},
                            graph_name=target_graph,
                        )
                        nodes_created += 1
                        edges_created += 1

    return {
        "status": "success",
        "graph_name": target_graph,
        "rows_processed": len(rows),
        "domain_detected": "fraud" if is_fraud else ("security" if is_security else "general"),
        "nodes_ingested": nodes_created,
        "edges_ingested": edges_created,
    }
