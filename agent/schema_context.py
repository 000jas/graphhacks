from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from agent.mcp_client import MCPClientManager

logger = logging.getLogger("graphos.agent.schema_context")


@dataclass
class GraphProfile:
    """
    Runtime profile of the connected FalkorDB graph discovered via MCP.
    Maintains authoritative schema metadata, topological metrics, and property catalogs
    without any hardcoded domain assumptions.
    """
    graph_identity: str
    inferred_domain: str
    total_nodes: int
    total_edges: int
    density: float
    average_degree: float
    node_kinds: list[dict[str, Any]] = field(default_factory=list)
    relationship_types: list[dict[str, Any]] = field(default_factory=list)
    relationship_patterns: list[dict[str, Any]] = field(default_factory=list)
    property_catalog: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    anomalies: list[dict[str, Any]] = field(default_factory=list)
    capabilities: dict[str, str] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    discovered_at: float = field(default_factory=time.time)

    def is_stale(self, ttl_seconds: float = 300.0) -> bool:
        """Check if the cached schema profile has expired."""
        return (time.time() - self.discovered_at) > ttl_seconds

    def to_prompt_context(self) -> str:
        """
        Render a concise, domain-agnostic schema guide for injection into the LLM system prompt.
        Allows the model to reason about arbitrary entity kinds, relationship types, and properties.
        """
        lines = [
            "### Runtime Discovered Graph Schema & Characteristics:",
            f"- Connected Graph Target: `{self.graph_identity}`",
            f"- Observed Topology: {self.total_nodes} nodes, {self.total_edges} relationships (density: {self.density}, avg degree: {self.average_degree})",
            f"- Structural Domain Profile: {self.inferred_domain}",
        ]

        if self.node_kinds:
            kind_strs = [f"{k['kind']} ({k.get('count', 0)})" for k in self.node_kinds[:12]]
            lines.append(f"- Available Node Kinds / Labels: {', '.join(kind_strs)}")

        if self.relationship_types:
            rel_strs = [f"{r['type']} ({r.get('total_instances', 0)})" for r in self.relationship_types[:15]]
            lines.append(f"- Available Relationship Types: {', '.join(rel_strs)}")

        if self.relationship_patterns:
            patterns = [
                f"({p['source_kind']}) -[:{p['relationship_type']}]-> ({p['target_kind']})"
                for p in self.relationship_patterns[:10]
            ]
            lines.append("- Observed Connection Patterns:\n  * " + "\n  * ".join(patterns))

        if self.property_catalog:
            lines.append("- Discovered Entity Properties (Sampled):")
            for kind, props in list(self.property_catalog.items())[:8]:
                prop_names = [p["property_name"] for p in props[:8]]
                lines.append(f"  * `{kind}`: {', '.join(prop_names)}")

        if self.limitations:
            lines.append("- Known Graph Limitations:\n  * " + "\n  * ".join(self.limitations))

        lines.append(
            "\nNote: All investigation must strictly use the discovered labels, types, and properties above. "
            "Never assume entities or relationships that do not exist in this graph."
        )
        return "\n".join(lines)

    def to_summary_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return asdict(self)


class SchemaContextManager:
    """
    Manages runtime discovery and caching of graph schema profiles via MCP tools.
    Acts as the bridge between FalkorDB's actual graph state and the Agent's reasoning engine.
    """

    def __init__(self, ttl_seconds: float = 300.0) -> None:
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, GraphProfile] = {}

    def invalidate(self, graph_name: Optional[str] = None) -> None:
        """Invalidate the schema cache for a specific graph or all graphs."""
        if graph_name:
            self._cache.pop(graph_name, None)
        else:
            self._cache.clear()

    async def get_or_discover_profile(
        self,
        mcp_client: MCPClientManager,
        tenant_graph: str = "",
        force_refresh: bool = False,
        sample_size: int = 100,
    ) -> GraphProfile:
        """
        Retrieve cached profile or discover schema dynamically from the MCP server.
        """
        graph_key = tenant_graph or "default"
        cached = self._cache.get(graph_key)
        if not force_refresh and cached and not cached.is_stale(self.ttl_seconds):
            return cached

        profile = await self._discover(
            mcp_client=mcp_client,
            tenant_graph=tenant_graph,
            force_refresh=force_refresh,
            sample_size=sample_size,
        )
        self._cache[graph_key] = profile
        return profile

    async def _discover(
        self,
        mcp_client: MCPClientManager,
        tenant_graph: str = "",
        force_refresh: bool = False,
        sample_size: int = 100,
    ) -> GraphProfile:
        """Perform MCP schema discovery call."""
        start_t = time.time()
        logger.info(f"Initiating runtime schema discovery for graph '{tenant_graph or 'default'}' via MCP...")

        try:
            resp_str = await mcp_client.call_tool(
                "discover_graph_schema",
                {
                    "sample_size": sample_size,
                    "refresh_cache": force_refresh,
                    "tenant_graph": tenant_graph,
                },
            )
            data = json.loads(resp_str)
        except Exception as exc:
            logger.warning(f"MCP schema discovery failed ({exc}). Falling back to bounded defaults.")
            return GraphProfile(
                graph_identity=tenant_graph or "unknown",
                inferred_domain="Unspecified Graph",
                total_nodes=0,
                total_edges=0,
                density=0.0,
                average_degree=0.0,
                limitations=[f"Automated schema discovery failed: {exc}"],
                capabilities={"schema_discovery": "failed"},
            )

        metrics = data.get("structural_metrics", {})
        profile = GraphProfile(
            graph_identity=data.get("tenant_graph", tenant_graph or "default"),
            inferred_domain=data.get("inferred_domain", "Connected Knowledge Graph"),
            total_nodes=metrics.get("total_nodes", 0),
            total_edges=metrics.get("total_edges", 0),
            density=metrics.get("graph_density", 0.0),
            average_degree=metrics.get("average_degree", 0.0),
            node_kinds=data.get("node_kinds", []),
            relationship_types=data.get("relationship_types", []),
            relationship_patterns=data.get("relationship_patterns", []),
            property_catalog=data.get("property_catalog", {}),
            anomalies=data.get("schema_anomalies", []),
            capabilities={
                "schema_discovery": "available",
                "read_only_traversal": "available",
                "multi_hop_paths": "available",
                "graph_algorithms": "available",
            },
            limitations=[
                f"{a['anomaly_type']}: {a['description']}"
                for a in data.get("schema_anomalies", [])
                if a.get("severity") in ("HIGH", "CRITICAL")
            ],
            discovered_at=time.time(),
        )
        logger.info(
            f"Discovered schema for '{profile.graph_identity}' in {(time.time() - start_t) * 1000:.1f}ms: "
            f"{profile.total_nodes} nodes, {profile.total_edges} edges, {len(profile.node_kinds)} kinds."
        )
        return profile
