from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

logger = logging.getLogger("graphos.agent.evidence")


@dataclass
class EntityFact:
    """A grounded entity fact retrieved directly from the graph."""
    id: str
    name: str
    kind: str
    status: Optional[str] = None
    source_ref: Optional[str] = None
    properties: dict[str, Any] = field(default_factory=dict)
    classification: str = "FACT"


@dataclass
class RelationshipEdge:
    """A verified edge connecting two graph entities."""
    from_id: str
    relationship_type: str
    to_id: str
    source_record_id: Optional[str] = None
    observed_at: Optional[str] = None
    confidence: float = 1.0


@dataclass
class EvidencePathChain:
    """A verified multi-hop relationship path."""
    source_id: str
    target_id: str
    hop_count: int
    chain_names: list[str] = field(default_factory=list)
    relationships: list[str] = field(default_factory=list)
    edges: list[RelationshipEdge] = field(default_factory=list)
    classification: str = "DERIVED"


class EvidenceCollector:
    """Collects, categorizes, and organizes factual graph evidence returned by MCP tools."""

    def __init__(self) -> None:
        self.entities: dict[str, EntityFact] = {}
        self.edges: list[RelationshipEdge] = []
        self.paths: list[EvidencePathChain] = []
        self.policy_results: list[dict[str, Any]] = []
        self.unresolved_gaps: list[str] = []
        self.raw_observations_count = 0

    def ingest_tool_output(self, tool_name: str, arguments: dict[str, Any], output_text: str) -> None:
        """Parse structured outputs returned by GraphOS MCP tools and extract evidence."""
        self.raw_observations_count += 1
        if not output_text:
            return

        try:
            data = json.loads(output_text)
        except Exception:
            return

        if not isinstance(data, dict):
            return

        entities_list = data.get("entities")
        if isinstance(entities_list, list):
            for e in entities_list:
                if isinstance(e, dict):
                    eid = str(e.get("id") or e.get("code") or e.get("key") or e.get("sku") or "")
                    ename = str(e.get("name") or e.get("title") or e.get("label") or eid or "")
                    if eid or ename:
                        ident = eid or ename
                        self.entities[ident] = EntityFact(
                            id=ident,
                            name=ename or ident,
                            kind=e.get("kind") or "Node",
                            status=e.get("status") or e.get("state"),
                            source_ref=e.get("source_ref") or e.get("source"),
                            properties=e.get("properties") or e,
                        )

        if "entity" in data and isinstance(data["entity"], dict):
            e = data["entity"]
            eid = str(e.get("id") or e.get("code") or e.get("key") or e.get("sku") or "")
            ename = str(e.get("name") or e.get("title") or e.get("label") or eid or "")
            if eid or ename:
                ident = eid or ename
                self.entities[ident] = EntityFact(
                    id=ident,
                    name=ename or ident,
                    kind=e.get("kind") or "Node",
                    status=e.get("properties", {}).get("status") or e.get("status"),
                    source_ref=e.get("properties", {}).get("source_ref") or e.get("source_ref"),
                    properties=e.get("properties") or e,
                )

            for out_r in data.get("outgoing_relationships", []):
                tgt = out_r.get("target", {})
                r_type = out_r.get("type", "")
                ev = out_r.get("evidence", {})
                if tgt.get("id"):
                    self.edges.append(
                        RelationshipEdge(
                            from_id=eid,
                            relationship_type=r_type,
                            to_id=tgt["id"],
                            source_record_id=ev.get("source_record_id"),
                            observed_at=ev.get("observed_at"),
                            confidence=float(ev.get("confidence", 1.0)) if isinstance(ev.get("confidence"), (int, float)) else 1.0,
                        )
                    )
                    if tgt["id"] not in self.entities:
                        self.entities[tgt["id"]] = EntityFact(
                            id=tgt["id"],
                            name=tgt.get("name", tgt["id"]),
                            kind=tgt.get("kind", "Entity"),
                        )

            for in_r in data.get("incoming_relationships", []):
                src = in_r.get("source", {})
                r_type = in_r.get("type", "")
                ev = in_r.get("evidence", {})
                if src.get("id"):
                    self.edges.append(
                        RelationshipEdge(
                            from_id=src["id"],
                            relationship_type=r_type,
                            to_id=eid,
                            source_record_id=ev.get("source_record_id"),
                            observed_at=ev.get("observed_at"),
                            confidence=float(ev.get("confidence", 1.0)) if isinstance(ev.get("confidence"), (int, float)) else 1.0,
                        )
                    )
                    if src["id"] not in self.entities:
                        self.entities[src["id"]] = EntityFact(
                            id=src["id"],
                            name=src.get("name", src["id"]),
                            kind=src.get("kind", "Entity"),
                        )

        if tool_name == "find_shortest_evidence_path" and data.get("found"):
            p_nodes = data.get("path_nodes", [])
            p_edges = data.get("path_edges", [])
            chain_names = [n.get("name", n.get("id")) for n in p_nodes if isinstance(n, dict)]
            rel_types = [e.get("type") for e in p_edges if isinstance(e, dict)]

            edge_objs = []
            for e in p_edges:
                edge_objs.append(
                    RelationshipEdge(
                        from_id=e.get("from_id", ""),
                        relationship_type=e.get("type", ""),
                        to_id=e.get("to_id", ""),
                        source_record_id=e.get("source_record_id"),
                        observed_at=e.get("observed_at"),
                        confidence=float(e.get("confidence", 1.0)) if isinstance(e.get("confidence"), (int, float)) else 1.0,
                    )
                )

            self.paths.append(
                EvidencePathChain(
                    source_id=data.get("source_id", ""),
                    target_id=data.get("target_id", ""),
                    hop_count=data.get("hop_count", len(p_edges)),
                    chain_names=chain_names,
                    relationships=rel_types,
                    edges=edge_objs,
                )
            )

        if tool_name == "traverse_relationships" and "paths" in data:
            for p in data.get("paths", []):
                p_nodes = p.get("path_nodes", [])
                p_edges = p.get("path_edges", [])
                chain_names = [n.get("name", n.get("id")) for n in p_nodes if isinstance(n, dict)]
                rel_types = [e.get("type") for e in p_edges if isinstance(e, dict)]
                if chain_names:
                    self.paths.append(
                        EvidencePathChain(
                            source_id=data.get("start_entity_id", ""),
                            target_id=p.get("entity", {}).get("id", ""),
                            hop_count=p.get("depth", len(p_edges)),
                            chain_names=chain_names,
                            relationships=rel_types,
                        )
                    )

        if tool_name == "check_policy":
            self.policy_results.append({
                "action": data.get("action"),
                "target_id": data.get("target_id"),
                "verdict": data.get("verdict"),
                "allowed": data.get("allowed"),
                "reason": data.get("reason"),
                "violated_rules": data.get("violated_rules", []),
                "missing_prerequisites": data.get("missing_prerequisites", []),
            })

        missing_ids = data.get("missing_ids")
        if isinstance(missing_ids, list):
            for m in missing_ids:
                self.unresolved_gaps.append(f"Entity '{m}' was not found in the graph database.")

        if data.get("found") is False:
            msg = data.get("message") or f"Entity '{arguments.get('entity_id') or arguments.get('source_id')}' was not found."
            self.unresolved_gaps.append(msg)

    def generate_summary(self) -> dict[str, Any]:
        """Produce a structured evidence report summarizing verified graph findings."""
        verified_edges_count = len([e for e in self.edges if e.source_record_id])
        verif_rate = (
            round(verified_edges_count / max(1, len(self.edges)), 2)
            if self.edges
            else 1.0
        )

        return {
            "total_entities_verified": len(self.entities),
            "total_edges_inspected": len(self.edges),
            "total_paths_established": len(self.paths),
            "provenance_verification_rate": verif_rate,
            "entities": {eid: asdict(fact) for eid, fact in self.entities.items()},
            "key_paths": [asdict(p) for p in self.paths[:10]],
            "policy_evaluations": self.policy_results,
            "unresolved_gaps": list(set(self.unresolved_gaps)),
        }
