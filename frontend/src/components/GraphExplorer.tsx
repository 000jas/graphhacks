"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import { ZoomIn, ZoomOut, Maximize2, Info, ChevronRight, ShieldCheck, Layers, Eye, X, AlertTriangle } from "lucide-react";
import { EntityFact, RelationshipEdge, EvidencePath } from "../types";

interface GraphExplorerProps {
  entities: Record<string, EntityFact>;
  edges: RelationshipEdge[];
  keyPaths?: EvidencePath[];
  selectedNodeId?: string | null;
  onSelectNode?: (id: string | null) => void;
}

interface LayoutNode {
  id: string;
  name: string;
  kind: string;
  status?: string;
  isIsolated?: boolean;
  x: number;
  y: number;
  properties: Record<string, any>;
}

interface LayoutEdge {
  from: string;
  to: string;
  type: string;
  provenance?: string;
  confidence?: number;
}

const KIND_COLORS: Record<string, { bg: string; border: string; text: string; dot: string }> = {
  Account: { bg: "#eff6ff", border: "#3b82f6", text: "#1d4ed8", dot: "#2563eb" },
  Device: { bg: "#f5f3ff", border: "#8b5cf6", text: "#6d28d9", dot: "#7c3aed" },
  Network: { bg: "#ecfdf5", border: "#10b981", text: "#047857", dot: "#059669" },
  Service: { bg: "#eef2ff", border: "#6366f1", text: "#4338ca", dot: "#4f46e5" },
  Repository: { bg: "#fdf2f8", border: "#ec4899", text: "#be185d", dot: "#db2777" },
  PullRequest: { bg: "#fff7ed", border: "#f97316", text: "#c2410c", dot: "#ea580c" },
  Task: { bg: "#fefce8", border: "#eab308", text: "#a16207", dot: "#ca8a04" },
  Person: { bg: "#f0fdf4", border: "#22c55e", text: "#15803d", dot: "#16a34a" },
  SecurityVulnerability: { bg: "#fef2f2", border: "#ef4444", text: "#b91c1c", dot: "#dc2626" },
  IAMRole: { bg: "#f8fafc", border: "#64748b", text: "#334155", dot: "#475569" },
  DatabaseInstance: { bg: "#f0f9ff", border: "#0ea5e9", text: "#0369a1", dot: "#0284c7" },
  CloudRegion: { bg: "#faf5ff", border: "#a855f7", text: "#7e22ce", dot: "#9333ea" },
  AuditRecord: { bg: "#f1f5f9", border: "#94a3b8", text: "#475569", dot: "#64748b" },
};

function getKindStyle(kind?: string) {
  if (!kind) {
    return { bg: "#f8fafc", border: "#94a3b8", text: "#334155", dot: "#64748b" };
  }
  return (
    KIND_COLORS[kind] || {
      bg: "#eff6ff",
      border: "#60a5fa",
      text: "#1e40af",
      dot: "#3b82f6",
    }
  );
}

export function GraphExplorer({
  entities,
  edges,
  keyPaths = [],
  selectedNodeId,
  onSelectNode,
}: GraphExplorerProps) {
  const [activeNode, setActiveNode] = useState<LayoutNode | null>(null);
  const [activeEdge, setActiveEdge] = useState<LayoutEdge | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  // Compute node and edge layouts
  const { nodes, layoutEdges } = useMemo(() => {
    const entityList = Object.values(entities);
    if (entityList.length === 0) {
      return { nodes: [], layoutEdges: [] };
    }

    const width = 760;
    const height = 480;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) * 0.38;

    const count = entityList.length;
    const computedNodes: LayoutNode[] = entityList.map((ent, i) => {
      // Circular distribution for clean, non-overlapping clarity
      const angle = (i / count) * 2 * Math.PI - Math.PI / 2;
      const x = count === 1 ? centerX : centerX + radius * Math.cos(angle);
      const y = count === 1 ? centerY : centerY + radius * Math.sin(angle);

      return {
        id: ent.id,
        name: ent.name || ent.id,
        kind: ent.kind || (ent.labels && ent.labels[0]) || "Entity",
        status: ent.status,
        isIsolated: ent.is_isolated,
        x,
        y,
        properties: ent.properties || {},
      };
    });

    const nodeMap = new Map(computedNodes.map((n) => [n.id, n]));
    const computedEdges: LayoutEdge[] = [];

    // Extract edges from relationships
    edges.forEach((edge) => {
      if (nodeMap.has(edge.from_id) && nodeMap.has(edge.to_id)) {
        computedEdges.push({
          from: edge.from_id,
          to: edge.to_id,
          type: edge.relationship_type,
          provenance: edge.source_record_id,
          confidence: edge.confidence,
        });
      }
    });

    // Also extract verified edges from key paths if not already in edges
    keyPaths.forEach((path) => {
      if (path.chain_names && path.relationships) {
        for (let i = 0; i < path.relationships.length; i++) {
          const fromName = path.chain_names[i];
          const toName = path.chain_names[i + 1];
          const relType = path.relationships[i];

          const fromNode = computedNodes.find((n) => n.name === fromName || n.id === fromName);
          const toNode = computedNodes.find((n) => n.name === toName || n.id === toName);

          if (fromNode && toNode) {
            const exists = computedEdges.some(
              (e) => e.from === fromNode.id && e.to === toNode.id && e.type === relType
            );
            if (!exists) {
              computedEdges.push({
                from: fromNode.id,
                to: toNode.id,
                type: relType,
                provenance: "Verified Path Hop",
                confidence: 1.0,
              });
            }
          }
        }
      }
    });

    return { nodes: computedNodes, layoutEdges: computedEdges };
  }, [entities, edges, keyPaths]);

  // Synchronize external selectedNodeId
  useEffect(() => {
    if (selectedNodeId) {
      const match = nodes.find((n) => n.id === selectedNodeId);
      if (match) setActiveNode(match);
    }
  }, [selectedNodeId, nodes]);

  const handleNodeClick = (node: LayoutNode, e: React.MouseEvent) => {
    e.stopPropagation();
    setActiveNode(node);
    setActiveEdge(null);
    onSelectNode?.(node.id);
  };

  const handleEdgeClick = (edge: LayoutEdge, e: React.MouseEvent) => {
    e.stopPropagation();
    setActiveEdge(edge);
    setActiveNode(null);
  };

  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const onMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const onMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    }
  };

  const onMouseUp = () => {
    setIsDragging(false);
  };

  const nodeMap = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  if (nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-80 rounded-2xl border border-dashed border-[#71849e]/30 bg-[#f6faff] p-8 text-center">
        <div className="w-12 h-12 rounded-full bg-[#1678ef]/10 flex items-center justify-center text-[#1678ef] mb-3">
          <Layers className="w-6 h-6" />
        </div>
        <h4 className="text-base font-semibold text-[#102f58]">No Evidence Subgraph Discovered Yet</h4>
        <p className="text-sm text-[#71849e] max-w-sm mt-1">
          Start an investigation to dynamically explore multi-hop connections, entities, and verified relationship paths.
        </p>
      </div>
    );
  }

  return (
    <div className="relative rounded-2xl border border-[#4370aa]/20 bg-white shadow-sm overflow-hidden flex flex-col h-[520px]">
      {/* Top action bar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#4370aa]/15 bg-[#f6faff]/80 backdrop-blur-sm z-10">
        <div className="flex items-center gap-2">
          <span className="flex h-2 w-2 rounded-full bg-[#268cf5] animate-pulse" />
          <span className="text-xs font-semibold uppercase tracking-wider text-[#102f58]">
            Evidence Topology ({nodes.length} nodes · {layoutEdges.length} edges)
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setZoom((z) => Math.min(z + 0.2, 2.4))}
            title="Zoom In"
            className="p-1.5 rounded-lg border border-[#4370aa]/20 bg-white hover:bg-[#eff7ff] text-[#102f58] transition"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={() => setZoom((z) => Math.max(z - 0.2, 0.5))}
            title="Zoom Out"
            className="p-1.5 rounded-lg border border-[#4370aa]/20 bg-white hover:bg-[#eff7ff] text-[#102f58] transition"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={resetView}
            title="Fit to Screen"
            className="p-1.5 rounded-lg border border-[#4370aa]/20 bg-white hover:bg-[#eff7ff] text-[#102f58] transition"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* SVG Canvas */}
      <div
        ref={containerRef}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
        className={`flex-1 w-full h-full cursor-${isDragging ? "grabbing" : "grab"} select-none relative bg-gradient-to-b from-[#f8fbff] to-[#edf4fc]`}
      >
        <svg
          className="w-full h-full"
          viewBox="0 0 760 480"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: "center center",
            transition: isDragging ? "none" : "transform 0.15s ease-out",
          }}
        >
          <defs>
            <marker
              id="arrowhead"
              markerWidth="10"
              markerHeight="7"
              refX="24"
              refY="3.5"
              orient="auto"
            >
              <polygon points="0 0, 10 3.5, 0 7" fill="#268cf5" opacity="0.85" />
            </marker>
            <marker
              id="arrowhead-active"
              markerWidth="10"
              markerHeight="7"
              refX="24"
              refY="3.5"
              orient="auto"
            >
              <polygon points="0 0, 10 3.5, 0 7" fill="#1678ef" />
            </marker>
          </defs>

          {/* Render Edges */}
          {layoutEdges.map((edge, idx) => {
            const src = nodeMap.get(edge.from);
            const tgt = nodeMap.get(edge.to);
            if (!src || !tgt) return null;

            const isEdgeSelected =
              activeEdge?.from === edge.from &&
              activeEdge?.to === edge.to &&
              activeEdge?.type === edge.type;

            const midX = (src.x + tgt.x) / 2;
            const midY = (src.y + tgt.y) / 2;

            return (
              <g
                key={`edge-${idx}`}
                onClick={(e) => handleEdgeClick(edge, e)}
                className="cursor-pointer group"
              >
                {/* Thick invisible hit line for easy clicking */}
                <line
                  x1={src.x}
                  y1={src.y}
                  x2={tgt.x}
                  y2={tgt.y}
                  stroke="transparent"
                  strokeWidth="18"
                />
                {/* Visible relationship edge */}
                <line
                  x1={src.x}
                  y1={src.y}
                  x2={tgt.x}
                  y2={tgt.y}
                  stroke={isEdgeSelected ? "#1678ef" : "#268cf5"}
                  strokeWidth={isEdgeSelected ? "2.5" : "1.8"}
                  strokeOpacity={isEdgeSelected ? "1" : "0.75"}
                  strokeDasharray={edge.provenance ? "none" : "4 3"}
                  markerEnd={isEdgeSelected ? "url(#arrowhead-active)" : "url(#arrowhead)"}
                  className="transition-colors group-hover:stroke-[#1678ef]"
                />
                {/* Edge relationship badge */}
                <rect
                  x={midX - (edge.type.length * 3.4 + 8)}
                  y={midY - 9}
                  width={edge.type.length * 6.8 + 16}
                  height="18"
                  rx="9"
                  fill={isEdgeSelected ? "#1678ef" : "#ffffff"}
                  stroke={isEdgeSelected ? "#0a2852" : "#82c4ff"}
                  strokeWidth="1"
                  className="transition-all"
                />
                <text
                  x={midX}
                  y={midY + 3.5}
                  textAnchor="middle"
                  fill={isEdgeSelected ? "#ffffff" : "#0a2852"}
                  fontSize="8.5"
                  fontWeight="600"
                  fontFamily="sans-serif"
                  className="pointer-events-none select-none"
                >
                  {edge.type}
                </text>
              </g>
            );
          })}

          {/* Render Nodes */}
          {nodes.map((node) => {
            const isSelected = activeNode?.id === node.id;
            const style = getKindStyle(node.kind);

            return (
              <g
                key={node.id}
                transform={`translate(${node.x}, ${node.y})`}
                onClick={(e) => handleNodeClick(node, e)}
                className="cursor-pointer group"
              >
                {/* Outer halo on selection */}
                {isSelected && (
                  <circle
                    r="28"
                    fill="none"
                    stroke="#268cf5"
                    strokeWidth="3"
                    strokeOpacity="0.4"
                    className="animate-pulse"
                  />
                )}

                {/* Main node circle */}
                <circle
                  r="21"
                  fill={style.bg}
                  stroke={isSelected ? "#1678ef" : style.border}
                  strokeWidth={isSelected ? "3" : "2"}
                  className="transition-all filter drop-shadow-sm group-hover:brightness-95"
                />

                {/* Node kind dot */}
                <circle r="4.5" fill={style.dot} />

                {/* Node Label Card */}
                <g transform="translate(0, 32)">
                  <rect
                    x="-65"
                    y="0"
                    width="130"
                    height="20"
                    rx="10"
                    fill="#ffffff"
                    fillOpacity="0.95"
                    stroke={isSelected ? "#1678ef" : "rgba(67, 112, 170, 0.25)"}
                    strokeWidth={isSelected ? "1.5" : "1"}
                  />
                  <text
                    x="0"
                    y="13"
                    textAnchor="middle"
                    fill="#102f58"
                    fontSize="9.5"
                    fontWeight="600"
                    className="select-none pointer-events-none"
                  >
                    {node.name.length > 20 ? node.name.slice(0, 18) + "…" : node.name}
                  </text>
                </g>

                {/* Node Kind Tag */}
                <text
                  x="0"
                  y="-26"
                  textAnchor="middle"
                  fill="#71849e"
                  fontSize="8.5"
                  fontWeight="600"
                  className="select-none uppercase tracking-wider"
                >
                  {node.kind}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Floating Detail Drawer (Node) */}
        {activeNode && (
          <div className="absolute right-3 top-3 w-72 max-h-[85%] rounded-xl border border-[#4370aa]/20 bg-white/95 backdrop-blur-md shadow-xl p-4 overflow-y-auto text-xs z-20 animate-in fade-in slide-in-from-right-4 duration-200">
            <div className="flex items-center justify-between pb-2 border-b border-[#4370aa]/15">
              <span className="font-semibold text-sm text-[#102f58] truncate">{activeNode.name}</span>
              <button
                onClick={() => setActiveNode(null)}
                className="text-[#71849e] hover:text-[#102f58] p-1"
                aria-label="Close details"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="mt-2.5 space-y-2">
              <div>
                <span className="text-[10px] uppercase font-bold text-[#71849e]">Entity ID</span>
                <p className="font-mono text-[#102f58] break-all">{activeNode.id}</p>
              </div>

              <div>
                <span className="text-[10px] uppercase font-bold text-[#71849e]">Kind / Label</span>
                <p className="inline-block mt-0.5 px-2 py-0.5 rounded-full font-semibold bg-[#eff7ff] text-[#1678ef]">
                  {activeNode.kind}
                </p>
              </div>

              {activeNode.status && (
                <div>
                  <span className="text-[10px] uppercase font-bold text-[#71849e]">Status</span>
                  <p className="font-semibold text-[#102f58]">{activeNode.status}</p>
                </div>
              )}

              {activeNode.isIsolated && (
                <div className="p-2 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-[11px] flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                  <span>Isolated Node: 0 connected relationships verified in graph.</span>
                </div>
              )}

              {Object.keys(activeNode.properties).length > 0 && (
                <div className="pt-2 border-t border-[#4370aa]/15">
                  <span className="text-[10px] uppercase font-bold text-[#71849e]">Properties</span>
                  <div className="mt-1 space-y-1">
                    {Object.entries(activeNode.properties).map(([k, v]) => (
                      <div key={k} className="flex justify-between gap-2 py-0.5 border-b border-[#4370aa]/5">
                        <span className="text-[#71849e] font-medium">{k}:</span>
                        <span className="text-[#102f58] font-mono text-right truncate max-w-[140px]" title={String(v)}>
                          {String(v)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Floating Detail Drawer (Edge) */}
        {activeEdge && (
          <div className="absolute right-3 top-3 w-64 rounded-xl border border-[#4370aa]/20 bg-white/95 backdrop-blur-md shadow-xl p-4 text-xs z-20 animate-in fade-in duration-150">
            <div className="flex items-center justify-between pb-2 border-b border-[#4370aa]/15">
              <span className="font-semibold text-sm text-[#102f58]">Relationship Fact</span>
              <button onClick={() => setActiveEdge(null)} className="text-[#71849e] hover:text-[#102f58]" aria-label="Close edge details">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="mt-2 space-y-2">
              <div>
                <span className="text-[10px] uppercase font-bold text-[#71849e]">Type</span>
                <p className="font-semibold text-[#1678ef] text-sm">{activeEdge.type}</p>
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold text-[#71849e]">From Node</span>
                <p className="font-mono text-[#102f58]">{activeEdge.from}</p>
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold text-[#71849e]">To Node</span>
                <p className="font-mono text-[#102f58]">{activeEdge.to}</p>
              </div>
              {activeEdge.provenance && (
                <div>
                  <span className="text-[10px] uppercase font-bold text-[#71849e]">Provenance</span>
                  <p className="text-[#102f58]">{activeEdge.provenance}</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Bottom legend */}
      <div className="flex items-center justify-between px-4 py-2 border-t border-[#4370aa]/15 bg-[#f6faff]/80 text-[11px] text-[#71849e]">
        <span>Click any node or edge to inspect verified properties</span>
        <span>Drag canvas to pan · Scroll or controls to zoom</span>
      </div>
    </div>
  );
}
