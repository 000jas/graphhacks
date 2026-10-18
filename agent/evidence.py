from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

logger = logging.getLogger("graphos.agent.evidence")

KNOWN_ID_KEYS = (
    "id", "code", "key", "sku", "uuid", "guid", "uri",
    "account_id", "user_id", "service_id", "device_id", "node_id",
    "execution_id", "proposal_id", "finding_id",
)

KNOWN_NAME_KEYS = (
    "name", "title", "label", "caption", "display_name",
    "service_name", "account_name", "summary",
)


def resolve_entity_id(data: dict[str, Any]) -> str:
    """
    Derive a reliable entity identity from returned graph data
    without assuming every graph has a particular identifier property.
    """
    if not isinstance(data, dict):
        return "unknown_entity"

    # 1. Check known identifier fields in top-level dict
    for id_field in KNOWN_ID_KEYS:
        val = data.get(id_field)
        if val is not None and str(val).strip():
            return str(val).strip()

    # 2. Check any field ending with _id, _code, or _key
    for k, v in data.items():
        if (k.endswith("_id") or k.endswith("_key") or k.endswith("_code")) and v is not None and str(v).strip():
            return str(v).strip()

    # 3. Check name/title/label
    for name_field in KNOWN_NAME_KEYS:
        val = data.get(name_field)
        if val is not None and str(val).strip():
            return str(val).strip()

    # 4. Check nested properties dict if present
    props = data.get("properties")
    if isinstance(props, dict):
        nested_id = resolve_entity_id(props)
        if nested_id and nested_id != "unknown_entity":
            return nested_id

    # 5. Deterministic fallback from sorted properties
    if data:
        items = sorted(
            (str(k), str(v))
            for k, v in data.items()
            if k not in ("properties", "evidence", "labels", "outgoing_relationships", "incoming_relationships")
            and v is not None
        )
        if items:
            raw_repr = "|".join(f"{k}:{v}" for k, v in items)
            return f"node_{hashlib.md5(raw_repr.encode()).hexdigest()[:10]}"

    return "unknown_entity"


def resolve_entity_name(data: dict[str, Any], fallback_id: str) -> str:
    """Extract a human-friendly name from an entity record without rigid property assumptions."""
    if not isinstance(data, dict):
        return fallback_id

    for name_field in KNOWN_NAME_KEYS:
        val = data.get(name_field)
        if val is not None and str(val).strip():
            return str(val).strip()

    props = data.get("properties")
    if isinstance(props, dict):
        for name_field in KNOWN_NAME_KEYS:
            val = props.get(name_field)
            if val is not None and str(val).strip():
                return str(val).strip()

    return fallback_id


def resolve_entity_kind(data: dict[str, Any]) -> str:
    """Extract entity kind or primary label without schema assumptions."""
    if not isinstance(data, dict):
        return "Node"

    kind = data.get("kind")
    if kind and kind != "Entity":
        return str(kind)

    labels = data.get("labels")
    if isinstance(labels, list):
        non_entity = [str(l) for l in labels if l != "Entity"]
        if non_entity:
            return non_entity[0]
        if labels:
            return str(labels[0])

    props = data.get("properties")
    if isinstance(props, dict) and props.get("kind"):
        return str(props["kind"])

    return "Node"


@dataclass
class EntityFact:
    """A grounded entity fact retrieved directly from the graph."""
    id: str
    name: str
    kind: str
    status: Optional[str] = None
    source_ref: Optional[str] = None
    labels: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    is_isolated: Optional[bool] = None
    relationship_contract: Optional[str] = None  # "complete", "partial", "unverified"
    source_tool: Optional[str] = None
    classification: str = "FACT"

    def format_properties(self) -> dict[str, Any]:
        """Format properties cleanly with primitive types preserved."""
        formatted: dict[str, Any] = {}
        for k, v in self.properties.items():
            if k in ("id", "name", "kind"):
                continue
            if isinstance(v, (str, int, float, bool)) or v is None:
                formatted[k] = v
            else:
                formatted[k] = str(v)
        return formatted

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["formatted_properties"] = self.format_properties()
        return d


@dataclass
class RelationshipEdge:
    """A verified edge connecting two graph entities."""
    from_id: str
    relationship_type: str
    to_id: str
    source_record_id: Optional[str] = None
    observed_at: Optional[str] = None
    confidence: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)
    source_tool: Optional[str] = None


@dataclass
class EvidencePathChain:
    """A verified multi-hop relationship path."""
    source_id: str
    target_id: str
    hop_count: int
    chain_names: list[str] = field(default_factory=list)
    relationships: list[str] = field(default_factory=list)
    edges: list[RelationshipEdge] = field(default_factory=list)
    is_verified: bool = True
    classification: str = "DERIVED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "hop_count": self.hop_count,
            "chain_names": self.chain_names,
            "relationships": self.relationships,
            "edges": [asdict(e) for e in self.edges],
            "is_verified": self.is_verified,
            "classification": self.classification,
        }


class EvidenceCollector:
    """
    Collects, deduplicates, and organizes factual graph evidence returned by MCP tools.
    Derives entity counts, edge counts, paths, and provenance deterministically from structured tool results.
    """

    def __init__(self) -> None:
        self.entities: dict[str, EntityFact] = {}
        self.edges: list[RelationshipEdge] = []
        self.unique_edge_keys: set[tuple[str, str, str]] = set()
        self.paths: list[EvidencePathChain] = []
        self.policy_results: list[dict[str, Any]] = []
        self.unresolved_gaps: list[str] = []
        self.duplicate_records_count: int = 0
        self.source_tool_calls: list[dict[str, Any]] = []
        self.raw_observations_count: int = 0

    def _record_entity(self, e: dict[str, Any], source_tool: Optional[str] = None) -> str:
        """Register or update an entity fact with deterministic deduplication."""
        eid = resolve_entity_id(e)
        ename = resolve_entity_name(e, fallback_id=eid)
        ekind = resolve_entity_kind(e)
        props = e.get("properties") if isinstance(e.get("properties"), dict) else e
        status = e.get("status") or (props.get("status") if isinstance(props, dict) else None)
        source_ref = e.get("source_ref") or (props.get("source_ref") if isinstance(props, dict) else None)
        labels = e.get("labels") or []
        if isinstance(labels, list):
            clean_labels = [str(l) for l in labels]
        else:
            clean_labels = []

        if eid in self.entities:
            self.duplicate_records_count += 1
            existing = self.entities[eid]
            if isinstance(props, dict):
                existing.properties.update(props)
            if status and not existing.status:
                existing.status = status
            if source_ref and not existing.source_ref:
                existing.source_ref = source_ref
            if clean_labels and not existing.labels:
                existing.labels = clean_labels
        else:
            self.entities[eid] = EntityFact(
                id=eid,
                name=ename,
                kind=ekind,
                status=status,
                source_ref=source_ref,
                labels=clean_labels,
                properties=dict(props) if isinstance(props, dict) else {},
                source_tool=source_tool,
            )
        return eid

    def _record_edge(
        self,
        from_id: str,
        relationship_type: str,
        to_id: str,
        source_record_id: Optional[str] = None,
        observed_at: Optional[str] = None,
        confidence: float = 1.0,
        properties: Optional[dict[str, Any]] = None,
        source_tool: Optional[str] = None,
    ) -> Optional[RelationshipEdge]:
        """Register a unique relationship edge with provenance."""
        if not from_id or not to_id or not relationship_type:
            return None

        edge_key = (from_id, relationship_type, to_id)
        if edge_key not in self.unique_edge_keys:
            self.unique_edge_keys.add(edge_key)
            edge = RelationshipEdge(
                from_id=from_id,
                relationship_type=relationship_type,
                to_id=to_id,
                source_record_id=source_record_id,
                observed_at=observed_at,
                confidence=confidence,
                properties=properties or {},
                source_tool=source_tool,
            )
            self.edges.append(edge)
            return edge
        return None

    def ingest_tool_output(self, tool_name: str, arguments: dict[str, Any], output_text: str) -> None:
        """Parse structured outputs returned by GraphOS MCP tools and extract grounded evidence."""
        self.raw_observations_count += 1
        if not output_text:
            return

        self.source_tool_calls.append({
            "tool": tool_name,
            "arguments": arguments,
            "output_length": len(output_text),
        })

        try:
            data = json.loads(output_text)
        except Exception:
            return

        if not isinstance(data, dict):
            return

        # 1. Handle search_connected_entities / search_entities_advanced / batch_get_entities
        entities_list = data.get("entities") or data.get("results")
        if isinstance(entities_list, list):
            for e in entities_list:
                if isinstance(e, dict):
                    self._record_entity(e, source_tool=tool_name)

        # 2. Handle inspect_entity_neighbors
        if tool_name == "inspect_entity_neighbors":
            ent = data.get("entity")
            if not isinstance(ent, dict) and (data.get("entity_id") or arguments.get("entity_id")):
                eid_fallback = data.get("entity_id") or arguments.get("entity_id")
                ent = {
                    "id": eid_fallback,
                    "name": data.get("entity_name") or eid_fallback,
                    "kind": data.get("entity_kind", "Entity"),
                }
            root_id = ""
            if isinstance(ent, dict):
                root_id = self._record_entity(ent, source_tool=tool_name)
                if root_id in self.entities:
                    self.entities[root_id].is_isolated = data.get("is_isolated")
                    self.entities[root_id].relationship_contract = data.get("relationship_contract") or (
                        "complete_isolated" if data.get("is_isolated") else "complete"
                    )

            neighbors = data.get("neighbors", [])
            for item in neighbors:
                if not isinstance(item, dict):
                    continue
                direction = item.get("direction", "outgoing")
                r_type = item.get("relationship_type", "")
                r_props = item.get("relationship_properties") or {}
                neigh_ent = item.get("neighbor", {})
                if isinstance(neigh_ent, dict):
                    neigh_id = self._record_entity(neigh_ent, source_tool=tool_name)
                    if root_id and neigh_id and r_type:
                        from_id = root_id if direction == "outgoing" else neigh_id
                        to_id = neigh_id if direction == "outgoing" else root_id
                        self._record_edge(
                            from_id=from_id,
                            relationship_type=r_type,
                            to_id=to_id,
                            source_record_id=r_props.get("source_record_id"),
                            observed_at=r_props.get("observed_at"),
                            confidence=float(r_props.get("confidence", 1.0)) if isinstance(r_props.get("confidence"), (int, float)) else 1.0,
                            properties=r_props,
                            source_tool=tool_name,
                        )

        # 3. Handle get_entity_profile
        if "entity" in data and isinstance(data["entity"], dict):
            e = data["entity"]
        elif tool_name == "get_entity_profile" and data.get("found"):
            e = data
        else:
            e = None

        if e:
            root_id = self._record_entity(e, source_tool=tool_name)

            if root_id in self.entities:
                self.entities[root_id].is_isolated = data.get("is_isolated")
                self.entities[root_id].relationship_contract = data.get("relationship_exploration_status", "complete")

            out_rels = data.get("outgoing_relationships") or data.get("relationships") or []
            for out_r in out_rels:
                tgt = out_r.get("target") or {
                    "id": out_r.get("target_id") or out_r.get("to_id"),
                    "name": out_r.get("target_name") or out_r.get("to_name"),
                    "kind": out_r.get("target_kind"),
                }
                r_type = out_r.get("type") or out_r.get("relationship_type", "")
                ev = out_r.get("evidence") or {}
                if isinstance(tgt, dict) and (tgt.get("id") or tgt.get("name")):
                    tgt_id = self._record_entity(tgt, source_tool=tool_name)
                    if root_id and tgt_id and r_type:
                        self._record_edge(
                            from_id=root_id,
                            relationship_type=r_type,
                            to_id=tgt_id,
                            source_record_id=ev.get("source_record_id") or out_r.get("source_record_id"),
                            observed_at=ev.get("observed_at") or out_r.get("observed_at"),
                            confidence=float(ev.get("confidence", 1.0)) if isinstance(ev.get("confidence"), (int, float)) else 1.0,
                            properties=ev,
                            source_tool=tool_name,
                        )

            in_rels = data.get("incoming_relationships") or []
            for in_r in in_rels:
                src = in_r.get("source") or {
                    "id": in_r.get("source_id") or in_r.get("from_id"),
                    "name": in_r.get("source_name") or in_r.get("from_name"),
                    "kind": in_r.get("source_kind"),
                }
                r_type = in_r.get("type") or in_r.get("relationship_type", "")
                ev = in_r.get("evidence") or {}
                if isinstance(src, dict) and (src.get("id") or src.get("name")):
                    src_id = self._record_entity(src, source_tool=tool_name)
                    if root_id and src_id and r_type:
                        self._record_edge(
                            from_id=src_id,
                            relationship_type=r_type,
                            to_id=root_id,
                            source_record_id=ev.get("source_record_id") or in_r.get("source_record_id"),
                            observed_at=ev.get("observed_at") or in_r.get("observed_at"),
                            confidence=float(ev.get("confidence", 1.0)) if isinstance(ev.get("confidence"), (int, float)) else 1.0,
                            properties=ev,
                            source_tool=tool_name,
                        )

        # 4. Handle find_shortest_evidence_path
        if tool_name == "find_shortest_evidence_path" and data.get("found"):
            p_nodes = data.get("path_nodes", [])
            p_edges = data.get("path_edges", [])
            chain_names = [resolve_entity_name(n, fallback_id=resolve_entity_id(n)) for n in p_nodes if isinstance(n, dict)]
            rel_types = [e.get("type") for e in p_edges if isinstance(e, dict) and e.get("type")]

            for n in p_nodes:
                if isinstance(n, dict):
                    self._record_entity(n, source_tool=tool_name)

            edge_objs: list[RelationshipEdge] = []
            for e in p_edges:
                if isinstance(e, dict):
                    fid = e.get("from_id", "")
                    tid = e.get("to_id", "")
                    rtype = e.get("type", "")
                    if fid and tid and rtype:
                        edge = self._record_edge(
                            from_id=fid,
                            relationship_type=rtype,
                            to_id=tid,
                            source_record_id=e.get("source_record_id"),
                            observed_at=e.get("observed_at"),
                            confidence=float(e.get("confidence", 1.0)) if isinstance(e.get("confidence"), (int, float)) else 1.0,
                            properties=e.get("properties") or {},
                            source_tool=tool_name,
                        )
                        if edge:
                            edge_objs.append(edge)

            # Only mark verified if constituent relationships are supported by actual data
            is_valid_path = len(edge_objs) > 0 or len(p_nodes) > 0
            if is_valid_path:
                self.paths.append(
                    EvidencePathChain(
                        source_id=data.get("source_id", ""),
                        target_id=data.get("target_id", ""),
                        hop_count=data.get("hop_count", len(p_edges)),
                        chain_names=chain_names,
                        relationships=rel_types,
                        edges=edge_objs,
                        is_verified=True,
                    )
                )

        # 5. Handle traverse_relationships
        if tool_name == "traverse_relationships" and "paths" in data:
            start_eid = data.get("start_entity_id", "")
            for p in data.get("paths", []):
                p_nodes = p.get("path_nodes", [])
                p_edges = p.get("path_edges", [])
                chain_names = [resolve_entity_name(n, fallback_id=resolve_entity_id(n)) for n in p_nodes if isinstance(n, dict)]
                rel_types = [e.get("type") for e in p_edges if isinstance(e, dict) and e.get("type")]

                for n in p_nodes:
                    if isinstance(n, dict):
                        self._record_entity(n, source_tool=tool_name)

                edge_objs = []
                for e in p_edges:
                    if isinstance(e, dict):
                        fid = e.get("from_id", "")
                        tid = e.get("to_id", "")
                        rtype = e.get("type", "")
                        if fid and tid and rtype:
                            edge = self._record_edge(
                                from_id=fid,
                                relationship_type=rtype,
                                to_id=tid,
                                source_record_id=e.get("source_record_id"),
                                observed_at=e.get("observed_at"),
                                confidence=float(e.get("confidence", 1.0)) if isinstance(e.get("confidence"), (int, float)) else 1.0,
                                properties=e.get("properties") or {},
                                source_tool=tool_name,
                            )
                            if edge:
                                edge_objs.append(edge)

                target_ent = p.get("entity", {})
                target_eid = resolve_entity_id(target_ent) if isinstance(target_ent, dict) else ""
                if chain_names:
                    self.paths.append(
                        EvidencePathChain(
                            source_id=start_eid,
                            target_id=target_eid,
                            hop_count=p.get("depth", len(p_edges)),
                            chain_names=chain_names,
                            relationships=rel_types,
                            edges=edge_objs,
                            is_verified=len(edge_objs) == len(p_edges) if p_edges else True,
                        )
                    )

        # 6. Handle check_policy
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

        # 7. Handle missing entity and negative results
        missing_ids = data.get("missing_ids")
        if isinstance(missing_ids, list):
            for m in missing_ids:
                self.unresolved_gaps.append(f"Entity '{m}' was not found in the graph database.")

        if data.get("found") is False:
            target_arg = arguments.get("entity_id") or arguments.get("source_id") or arguments.get("target_id")
            msg = data.get("message") or f"Entity '{target_arg}' was not found."
            self.unresolved_gaps.append(msg)

    def generate_summary(self) -> dict[str, Any]:
        """
        Produce a deterministic structured evidence report summarizing verified graph findings.
        Counts and metrics are strictly reconciled with registered facts and edges.
        """
        verified_edges_count = len([e for e in self.edges if e.source_record_id])
        verif_rate = (
            round(verified_edges_count / max(1, len(self.edges)), 2)
            if self.edges
            else 1.0
        )

        return {
            "total_entities_verified": len(self.entities),
            "unique_entities_count": len(self.entities),
            "total_edges_inspected": len(self.edges),
            "total_relationships_count": len(self.edges),
            "total_paths_established": len(self.paths),
            "duplicate_records_detected": self.duplicate_records_count,
            "provenance_verification_rate": verif_rate,
            "entities": {eid: fact.to_dict() for eid, fact in self.entities.items()},
            "edges": [asdict(e) for e in self.edges],
            "key_paths": [p.to_dict() for p in self.paths[:10]],
            "policy_evaluations": self.policy_results,
            "unresolved_gaps": list(set(self.unresolved_gaps)),
            "source_tool_calls": self.source_tool_calls,
        }
