"use client";

import React, { useState, useEffect, useMemo, useRef, useCallback } from "react";
import {
  forceSimulation,
  forceManyBody,
  forceLink,
  forceCenter,
  forceCollide,
  Simulation,
} from "d3-force";
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  Info,
  ChevronRight,
  ShieldCheck,
  Layers,
  Eye,
  X,
  AlertTriangle,
  Move,
  RefreshCw,
} from "lucide-react";
import { EntityFact, RelationshipEdge, EvidencePath } from "../types";

interface GraphExplorerProps {
  entities: Record<string, EntityFact>;
  edges: RelationshipEdge[];
  keyPaths?: EvidencePath[];
  selectedNodeId?: string | null;
  onSelectNode?: (id: string | null) => void;
}

interface SimNode {
  id: string;
  name: string;
  kind: string;
  status?: string;
  isIsolated?: boolean;
  properties: Record<string, any>;
  x: number;
  y: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
}

interface SimLink {
  source: string | SimNode;
  target: string | SimNode;
  type: string;
  confidence?: number;
  provenance?: string;
}

const KIND_PALETTE: Record<
  string,
  { fill: string; stroke: string; text: string; glow: string; badgeBg: string }
> = {
  Account: {
    fill: "#2563eb",
    stroke: "#1d4ed8",
    text: "#ffffff",
    glow: "rgba(37, 99, 235, 0.4)",
    badgeBg: "#eff6ff",
  },
  Transaction: {
    fill: "#059669",
    stroke: "#047857",
    text: "#ffffff",
    glow: "rgba(5, 150, 105, 0.4)",
    badgeBg: "#ecfdf5",
  },
  Person: {
    fill: "#10b981",
    stroke: "#059669",
    text: "#ffffff",
    glow: "rgba(16, 185, 129, 0.4)",
    badgeBg: "#f0fdf4",
  },
  Device: {
    fill: "#7c3aed",
    stroke: "#6d28d9",
    text: "#ffffff",
    glow: "rgba(124, 58, 237, 0.4)",
    badgeBg: "#f5f3ff",
  },
  Ip: {
    fill: "#0284c7",
    stroke: "#0369a1",
    text: "#ffffff",
    glow: "rgba(2, 132, 199, 0.4)",
    badgeBg: "#f0f9ff",
  },
  Host: {
    fill: "#6366f1",
    stroke: "#4f46e5",
    text: "#ffffff",
    glow: "rgba(99, 102, 241, 0.4)",
    badgeBg: "#eef2ff",
  },
  Service: {
    fill: "#4f46e5",
    stroke: "#4338ca",
    text: "#ffffff",
    glow: "rgba(79, 70, 229, 0.4)",
    badgeBg: "#eef2ff",
  },
  Repository: {
    fill: "#db2777",
    stroke: "#be185d",
    text: "#ffffff",
    glow: "rgba(219, 39, 119, 0.4)",
    badgeBg: "#fdf2f8",
  },
  File: {
    fill: "#0891b2",
    stroke: "#0e7490",
    text: "#ffffff",
    glow: "rgba(8, 145, 178, 0.4)",
    badgeBg: "#ecfeff",
  },
  Function: {
    fill: "#0d9488",
    stroke: "#0f766e",
    text: "#ffffff",
    glow: "rgba(13, 148, 136, 0.4)",
    badgeBg: "#f0fdfa",
  },
  Class: {
    fill: "#9333ea",
    stroke: "#7e22ce",
    text: "#ffffff",
    glow: "rgba(147, 51, 234, 0.4)",
    badgeBg: "#faf5ff",
  },
  Externaldependency: {
    fill: "#c026d3",
    stroke: "#a21caf",
    text: "#ffffff",
    glow: "rgba(192, 38, 211, 0.4)",
    badgeBg: "#fdf4ff",
  },
  Vulnerability: {
    fill: "#dc2626",
    stroke: "#b91c1c",
    text: "#ffffff",
    glow: "rgba(220, 38, 38, 0.5)",
    badgeBg: "#fef2f2",
  },
  Alert: {
    fill: "#ea580c",
    stroke: "#c2410c",
    text: "#ffffff",
    glow: "rgba(234, 88, 12, 0.4)",
    badgeBg: "#fff7ed",
  },
  Incident: {
    fill: "#e11d48",
    stroke: "#be123c",
    text: "#ffffff",
    glow: "rgba(225, 29, 72, 0.5)",
    badgeBg: "#fff1f2",
  },
  Address: {
    fill: "#0ea5e9",
    stroke: "#0284c7",
    text: "#ffffff",
    glow: "rgba(14, 165, 233, 0.4)",
    badgeBg: "#f0f9ff",
  },
  Policy: {
    fill: "#d97706",
    stroke: "#b45309",
    text: "#ffffff",
    glow: "rgba(217, 119, 6, 0.4)",
    badgeBg: "#fffbeb",
  },
  AuditRecord: {
    fill: "#64748b",
    stroke: "#475569",
    text: "#ffffff",
    glow: "rgba(100, 116, 139, 0.4)",
    badgeBg: "#f8fafc",
  },
};

const DEFAULT_PALETTE = {
  fill: "#3b82f6",
  stroke: "#1d4ed8",
  text: "#ffffff",
  glow: "rgba(59, 130, 246, 0.4)",
  badgeBg: "#eff6ff",
};

export function GraphExplorer({
  entities,
  edges,
  keyPaths = [],
  selectedNodeId,
  onSelectNode,
}: GraphExplorerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [nodes, setNodes] = useState<SimNode[]>([]);
  const [links, setLinks] = useState<SimLink[]>([]);
  const [activeNode, setActiveNode] = useState<SimNode | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  // Pan & Zoom
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });

  // Dragging node
  const [draggedNode, setDraggedNode] = useState<SimNode | null>(null);
  const simulationRef = useRef<Simulation<SimNode, any> | null>(null);

  const NODE_RADIUS = 24;
  const CANVAS_WIDTH = 800;
  const CANVAS_HEIGHT = 520;

  // Sync selectedNodeId prop with activeNode state
  useEffect(() => {
    if (selectedNodeId) {
      const match = nodes.find((n) => n.id === selectedNodeId || n.name === selectedNodeId);
      if (match) setActiveNode(match);
    }
  }, [selectedNodeId, nodes]);

  // Construct raw nodes and links from props and auto-derived paths
  const rawData = useMemo(() => {
    const entList = Object.values(entities);
    if (entList.length === 0) return { nodes: [], links: [] };

    const initialNodes: SimNode[] = entList.map((ent, i) => {
      // Natural initial scatter around center
      const angle = (i / entList.length) * 2 * Math.PI;
      const dist = 120 + (i % 3) * 45;
      return {
        id: ent.id,
        name: ent.name || ent.id,
        kind: ent.kind || (ent.labels && ent.labels[0]) || "Entity",
        status: ent.status,
        isIsolated: ent.is_isolated,
        properties: ent.properties || {},
        x: CANVAS_WIDTH / 2 + dist * Math.cos(angle) + (Math.random() - 0.5) * 20,
        y: CANVAS_HEIGHT / 2 + dist * Math.sin(angle) + (Math.random() - 0.5) * 20,
      };
    });

    const nodeIds = new Set(initialNodes.map((n) => n.id));
    const nodeNames = new Map(initialNodes.map((n) => [n.name, n.id]));
    const linkList: SimLink[] = [];
    const linkKeys = new Set<string>();

    const addLink = (from: string, to: string, type: string, confidence = 1.0) => {
      const actualFrom = nodeIds.has(from) ? from : nodeNames.get(from);
      const actualTo = nodeIds.has(to) ? to : nodeNames.get(to);
      if (actualFrom && actualTo && actualFrom !== actualTo) {
        const key = `${actualFrom}__${type}__${actualTo}`;
        if (!linkKeys.has(key)) {
          linkKeys.add(key);
          linkList.push({
            source: actualFrom,
            target: actualTo,
            type,
            confidence,
          });
        }
      }
    };

    // 1. Direct edges
    edges.forEach((e) => {
      addLink(e.from_id, e.to_id, e.relationship_type, e.confidence);
    });

    // 2. Traversed keyPaths
    keyPaths.forEach((path) => {
      if (path.chain_names && path.relationships) {
        for (let i = 0; i < path.relationships.length; i++) {
          const from = path.chain_ids?.[i] || path.chain_names[i];
          const to = path.chain_ids?.[i + 1] || path.chain_names[i + 1];
          const rel = path.relationships[i];
          if (from && to && rel) {
            addLink(from, to, rel);
          }
        }
      }
    });

    return { nodes: initialNodes, links: linkList };
  }, [entities, edges, keyPaths]);

  // Run d3-force physics simulation
  useEffect(() => {
    if (rawData.nodes.length === 0) {
      setNodes([]);
      setLinks([]);
      return;
    }

    // Clone to prevent mutating props
    const simNodes: SimNode[] = rawData.nodes.map((n) => ({ ...n }));
    const simLinks: SimLink[] = rawData.links.map((l) => ({ ...l }));

    if (simulationRef.current) {
      simulationRef.current.stop();
    }

    const sim = forceSimulation<SimNode>(simNodes)
      .force(
        "link",
        forceLink<SimNode, any>(simLinks)
          .id((d) => d.id)
          .distance((l: any) => 110)
          .strength(0.6)
      )
      .force("charge", forceManyBody().strength(-380).distanceMax(450))
      .force("center", forceCenter(CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2).strength(0.08))
      .force("collision", forceCollide().radius(NODE_RADIUS + 18).strength(0.85))
      .alphaDecay(0.035);

    sim.on("tick", () => {
      setNodes([...simNodes]);
      setLinks([...simLinks]);
    });

    simulationRef.current = sim;

    return () => {
      sim.stop();
    };
  }, [rawData]);

  // Node Drag handlers (FalkorDB / Bloom interactive physics)
  const handleNodeMouseDown = (e: React.MouseEvent, node: SimNode) => {
    e.stopPropagation();
    setDraggedNode(node);
    node.fx = node.x;
    node.fy = node.y;
    if (simulationRef.current) {
      simulationRef.current.alphaTarget(0.3).restart();
    }
  };

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (draggedNode && containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        // Convert screen coordinates to canvas space considering zoom and pan
        const mouseX = (e.clientX - rect.left - pan.x) / zoom;
        const mouseY = (e.clientY - rect.top - pan.y) / zoom;
        draggedNode.fx = mouseX;
        draggedNode.fy = mouseY;
      } else if (isPanning) {
        setPan({
          x: e.clientX - panStart.x,
          y: e.clientY - panStart.y,
        });
      }
    },
    [draggedNode, isPanning, panStart, pan, zoom]
  );

  const handleMouseUp = useCallback(() => {
    if (draggedNode) {
      // Release pin or let settle
      draggedNode.fx = null;
      draggedNode.fy = null;
      setDraggedNode(null);
      if (simulationRef.current) {
        simulationRef.current.alphaTarget(0);
      }
    }
    setIsPanning(false);
  }, [draggedNode]);

  // Pan Canvas
  const handleCanvasMouseDown = (e: React.MouseEvent) => {
    if (e.button === 0) {
      setIsPanning(true);
      setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    if (simulationRef.current) {
      simulationRef.current.alpha(0.6).restart();
    }
  };

  const handleNodeClick = (node: SimNode) => {
    setActiveNode(node);
    if (onSelectNode) {
      onSelectNode(node.id);
    }
  };

  return (
    <div className="flex flex-col h-[520px] rounded-3xl border border-[#4370aa]/20 bg-white overflow-hidden shadow-md relative">
      {/* Top status & controls bar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#4370aa]/15 bg-white/95 backdrop-blur-md z-10">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-blue-600 animate-pulse" />
          <span className="font-bold text-xs text-[#102f58]">
            Topology Graph ({nodes.length} nodes • {links.length} relationships)
          </span>
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200/60 hidden sm:inline">
            Force Physics
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setZoom((z) => Math.min(z + 0.2, 2.5))}
            title="Zoom In"
            className="p-1.5 rounded-lg border border-[#4370aa]/20 bg-white hover:bg-[#eff7ff] text-[#102f58] transition cursor-pointer"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setZoom((z) => Math.max(z - 0.2, 0.4))}
            title="Zoom Out"
            className="p-1.5 rounded-lg border border-[#4370aa]/20 bg-white hover:bg-[#eff7ff] text-[#102f58] transition cursor-pointer"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={resetView}
            title="Center and Reset Simulation"
            className="p-1.5 rounded-lg border border-[#4370aa]/20 bg-white hover:bg-[#eff7ff] text-[#102f58] transition cursor-pointer"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Interactive SVG Canvas */}
      <div
        ref={containerRef}
        onMouseDown={handleCanvasMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        className={`flex-1 w-full h-full relative overflow-hidden bg-gradient-to-br from-[#f8fbff] via-[#f2f7fd] to-[#edf4fc] select-none cursor-${
          isPanning ? "grabbing" : draggedNode ? "move" : "grab"
        }`}
      >
        {/* Subtle grid pattern background */}
        <div
          className="absolute inset-0 pointer-events-none opacity-40"
          style={{
            backgroundImage:
              "radial-gradient(circle, #3b82f6 1px, transparent 1px)",
            backgroundSize: "28px 28px",
          }}
        />

        <svg
          className="w-full h-full"
          viewBox={`0 0 ${CANVAS_WIDTH} ${CANVAS_HEIGHT}`}
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: "center center",
            transition: isPanning || draggedNode ? "none" : "transform 0.15s ease-out",
          }}
        >
          <defs>
            <marker
              id="falkor-arrow"
              viewBox="0 0 10 10"
              refX="10"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="#64748b" />
            </marker>
            <marker
              id="falkor-arrow-active"
              viewBox="0 0 10 10"
              refX="10"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 10 5 L 0 9 z" fill="#2563eb" />
            </marker>
          </defs>

          {/* Render Relationship Links */}
          <g className="links">
            {links.map((link, idx) => {
              const src = typeof link.source === "object" ? link.source : null;
              const tgt = typeof link.target === "object" ? link.target : null;
              if (!src || !tgt) return null;

              const dx = tgt.x - src.x;
              const dy = tgt.y - src.y;
              const dist = Math.sqrt(dx * dx + dy * dy) || 1;

              // Clip link ends to node circles so arrow points at circumference
              const padding = NODE_RADIUS + 2;
              const startX = src.x + (dx * padding) / dist;
              const startY = src.y + (dy * padding) / dist;
              const endX = tgt.x - (dx * (padding + 6)) / dist;
              const endY = tgt.y - (dy * (padding + 6)) / dist;

              const midX = (startX + endX) / 2;
              const midY = (startY + endY) / 2;

              const isConnectedToHovered =
                hoveredNodeId === src.id || hoveredNodeId === tgt.id;
              const isConnectedToActive =
                activeNode?.id === src.id || activeNode?.id === tgt.id;
              const isHighlight = isConnectedToHovered || isConnectedToActive;

              return (
                <g key={`link-${idx}`} className="group">
                  {/* Link line */}
                  <line
                    x1={startX}
                    y1={startY}
                    x2={endX}
                    y2={endY}
                    stroke={isHighlight ? "#2563eb" : "#94a3b8"}
                    strokeWidth={isHighlight ? 2.5 : 1.5}
                    strokeOpacity={isHighlight ? 1 : 0.65}
                    markerEnd={
                      isHighlight
                        ? "url(#falkor-arrow-active)"
                        : "url(#falkor-arrow)"
                    }
                    className="transition-colors"
                  />

                  {/* Relationship label pill in middle of line */}
                  {link.type && (
                    <g transform={`translate(${midX}, ${midY})`}>
                      <rect
                        x={-(link.type.length * 3.3 + 7)}
                        y="-8.5"
                        width={link.type.length * 6.6 + 14}
                        height="17"
                        rx="8.5"
                        fill={isHighlight ? "#1e40af" : "#ffffff"}
                        stroke={isHighlight ? "#1d4ed8" : "#cbd5e1"}
                        strokeWidth="1"
                        className="shadow-xs transition-colors"
                      />
                      <text
                        textAnchor="middle"
                        y="3.5"
                        fill={isHighlight ? "#ffffff" : "#475569"}
                        fontSize="8.5"
                        fontWeight="700"
                        fontFamily="sans-serif"
                        className="pointer-events-none select-none"
                      >
                        {link.type}
                      </text>
                    </g>
                  )}
                </g>
              );
            })}
          </g>

          {/* Render FalkorDB-style Nodes */}
          <g className="nodes">
            {nodes.map((node) => {
              const isSelected = activeNode?.id === node.id;
              const isHovered = hoveredNodeId === node.id;
              const palette = KIND_PALETTE[node.kind] || DEFAULT_PALETTE;

              const labelText =
                node.name && node.name.length > 14
                  ? `${node.name.slice(0, 12)}…`
                  : node.name || node.id;

              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x}, ${node.y})`}
                  onMouseDown={(e) => handleNodeMouseDown(e, node)}
                  onClick={() => handleNodeClick(node)}
                  onMouseEnter={() => setHoveredNodeId(node.id)}
                  onMouseLeave={() => setHoveredNodeId(null)}
                  className="cursor-pointer group"
                >
                  {/* Outer glowing halo on hover / select */}
                  {(isSelected || isHovered) && (
                    <circle
                      r={NODE_RADIUS + 7}
                      fill="none"
                      stroke={palette.fill}
                      strokeWidth="3.5"
                      strokeOpacity="0.45"
                      className="animate-pulse"
                    />
                  )}

                  {/* Main colorful node bubble */}
                  <circle
                    r={NODE_RADIUS}
                    fill={palette.fill}
                    stroke="#ffffff"
                    strokeWidth="2.5"
                    className="transition-transform group-hover:scale-105 shadow-md"
                    style={{
                      filter: `drop-shadow(0 4px 10px ${palette.glow})`,
                    }}
                  />

                  {/* Node short name or initials inside the circle */}
                  <text
                    textAnchor="middle"
                    y="3.5"
                    fill={palette.text}
                    fontSize="9.5"
                    fontWeight="800"
                    fontFamily="sans-serif"
                    className="select-none pointer-events-none"
                  >
                    {node.name.length <= 4
                      ? node.name
                      : node.id.slice(0, 4)}
                  </text>

                  {/* Label badge pill below node */}
                  <g transform={`translate(0, ${NODE_RADIUS + 13})`}>
                    <rect
                      x={-(labelText.length * 3.4 + 9)}
                      y="-8"
                      width={labelText.length * 6.8 + 18}
                      height="17"
                      rx="8.5"
                      fill="#ffffff"
                      stroke={isSelected ? palette.fill : "#cbd5e1"}
                      strokeWidth={isSelected ? "1.5" : "1"}
                      className="shadow-xs"
                    />
                    <text
                      textAnchor="middle"
                      y="4"
                      fill="#0f172a"
                      fontSize="9"
                      fontWeight="700"
                      className="select-none pointer-events-none"
                    >
                      {labelText}
                    </text>
                  </g>

                  {/* Node Kind Tag on top */}
                  <text
                    textAnchor="middle"
                    y={-(NODE_RADIUS + 6)}
                    fill="#64748b"
                    fontSize="8"
                    fontWeight="800"
                    className="select-none pointer-events-none uppercase tracking-wider"
                  >
                    :{node.kind}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>

        {/* Floating Detail Drawer (Node Properties) */}
        {activeNode && (
          <div className="absolute right-3 top-3 w-72 max-h-[90%] rounded-2xl border border-slate-200 bg-white/95 backdrop-blur-md shadow-2xl p-4 overflow-y-auto text-xs z-20 animate-in fade-in slide-in-from-right-4 duration-200">
            <div className="flex items-center justify-between pb-2 border-b border-slate-200">
              <div className="flex items-center gap-1.5 truncate">
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{
                    backgroundColor:
                      (KIND_PALETTE[activeNode.kind] || DEFAULT_PALETTE).fill,
                  }}
                />
                <span className="font-extrabold text-sm text-[#0a2852] truncate">
                  {activeNode.name}
                </span>
              </div>
              <button
                onClick={() => setActiveNode(null)}
                className="text-slate-400 hover:text-slate-700 p-1 rounded-md"
                aria-label="Close details"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="mt-3 space-y-2.5">
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400">
                  Node Identifier
                </span>
                <p className="font-mono text-slate-900 font-semibold break-all bg-slate-50 p-1.5 rounded-lg border border-slate-200">
                  {activeNode.id}
                </p>
              </div>

              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400">
                  Entity Label
                </span>
                <p className="inline-block mt-0.5 px-2.5 py-0.5 rounded-full font-bold text-xs bg-blue-50 text-blue-700 border border-blue-200">
                  :{activeNode.kind}
                </p>
              </div>

              {activeNode.status && (
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">
                    Status
                  </span>
                  <p className="font-semibold text-slate-800 capitalize">
                    {activeNode.status}
                  </p>
                </div>
              )}

              {Object.keys(activeNode.properties).length > 0 && (
                <div className="pt-2 border-t border-slate-100">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">
                    Graph Properties
                  </span>
                  <div className="bg-slate-50 rounded-xl p-2.5 border border-slate-200 space-y-1 font-mono text-[11px]">
                    {Object.entries(activeNode.properties).map(([k, v]) => (
                      <div key={k} className="flex justify-between gap-2">
                        <span className="text-slate-500 truncate">{k}:</span>
                        <span className="text-slate-900 font-semibold truncate text-right">
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

        {/* Empty state overlay if zero entities */}
        {nodes.length === 0 && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-6 bg-slate-50/80 backdrop-blur-xs">
            <Layers className="w-10 h-10 text-slate-300 mb-3" />
            <h4 className="font-bold text-sm text-[#0a2852]">
              No Graph Nodes Selected
            </h4>
            <p className="text-xs text-slate-500 max-w-sm mt-1">
              Select a graph from the dropdown or submit an investigation query to visualize entity clusters and relationship edges.
            </p>
          </div>
        )}
      </div>

      {/* Bottom hint helper */}
      <div className="px-4 py-2 border-t border-slate-100 bg-slate-50/70 text-[11px] text-slate-500 flex items-center justify-between">
        <span>Click & drag bubbles to untangle • Click to inspect properties</span>
        <span className="font-semibold text-blue-600">FalkorDB Force Physics</span>
      </div>
    </div>
  );
}
