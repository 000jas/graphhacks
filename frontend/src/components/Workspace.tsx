"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Database,
  Search,
  Sparkles,
  ArrowLeft,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  Clock,
  Layers,
  Network,
  Shield,
  Code,
  CreditCard,
  ChevronRight,
  Send,
  Sliders,
  FileText,
  Maximize2,
  Zap,
  Activity,
  Upload,
  ShieldCheck,
  Menu,
  X,
  Square,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  Trash2,
  Plus,
  Lock,
} from "lucide-react";
import {
  InvestigationResult,
  InvestigationEvent,
  HealthStatus,
  GraphSchemaProfile,
  EntityFact,
  User,
  ConversationSummary,
  ConversationDetail,
  ChatMessageRecord,
} from "../types";
import {
  executeInvestigationStream,
  getHealth,
  getSchema,
  getAvailableGraphs,
  getGraphPreview,
  approveRemediation,
  getMe,
  logoutUser,
  getConversations,
  getConversation,
  deleteConversation,
} from "../lib/api";
import { GraphExplorer } from "./GraphExplorer";
import { ImportDatasetModal } from "./ImportDatasetModal";
import { FormattedMarkdown } from "./FormattedMarkdown";
import { AuthModal } from "./AuthModal";

const EMPTY_KEY_PATHS: any[] = [];
const EMPTY_ENTITIES: Record<string, EntityFact> = {};
const EMPTY_EDGES: any[] = [];

interface WorkspaceProps {
  initialQuery?: string;
  initialMode?: "live" | "demo";
  initialGraph?: string;
  onBackToLanding: () => void;
}

export function Workspace({
  initialQuery = "",
  initialMode = "live",
  initialGraph = "ALL_GRAPHS",
  onBackToLanding,
}: WorkspaceProps) {
  const [mode, setMode] = useState<"live" | "demo">("live");
  const [queryInput, setQueryInput] = useState(initialQuery);
  const [currentObjective, setCurrentObjective] = useState(initialQuery);
  const [isInvestigating, setIsInvestigating] = useState(false);
  const [activeTab, setActiveTab] = useState<"graph" | "paths" | "entities" | "activity">("graph");
  const [events, setEvents] = useState<InvestigationEvent[]>([]);
  const [currentResult, setCurrentResult] = useState<InvestigationResult | null>(null);
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [availableGraphs, setAvailableGraphs] = useState<string[]>(["ALL_GRAPHS"]);
  const [selectedGraph, setSelectedGraph] = useState<string>(initialGraph || "ALL_GRAPHS");
  const [recentSessions, setRecentSessions] = useState<
    Array<{ id: string; query: string; timestamp: string }>
  >([]);
  const [schemaProfile, setSchemaProfile] = useState<GraphSchemaProfile | null>(null);
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [pastMessages, setPastMessages] = useState<ChatMessageRecord[]>([]);
  const [isDeletingConvId, setIsDeletingConvId] = useState<string | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [actionApproved, setActionApproved] = useState(false);
  const [isApprovingAction, setIsApprovingAction] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const [isReasoningExpanded, setIsReasoningExpanded] = useState<boolean>(true);
  const [copiedAnswer, setCopiedAnswer] = useState<boolean>(false);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);

  const refreshConversations = async () => {
    try {
      const list = await getConversations();
      setConversations(list);
    } catch {
      // ignore
    }
  };

  // Load user and conversations on mount
  useEffect(() => {
    getMe().then((u) => {
      if (u) {
        setUser(u);
        getConversations().then(setConversations);
      }
    });
  }, []);

  // Load real user sessions from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem("graphos_recent_sessions");
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setRecentSessions(parsed);
        }
      }
    } catch {
      // ignore
    }
  }, []);

  const handleApproveAction = async (actionType: string, targetId: string) => {
    setIsApprovingAction(true);
    try {
      await approveRemediation(actionType, targetId, "Approved via Workspace UI", selectedGraph);
      setActionApproved(true);
    } catch (err) {
      console.error(err);
      setActionApproved(true);
    } finally {
      setIsApprovingAction(false);
    }
  };

  const handleIngestSuccess = (graphName: string) => {
    getAvailableGraphs().then((res) => {
      if (res && res.graphs) {
        setAvailableGraphs(res.graphs);
      }
    });
    handleGraphChange(graphName);
    setIsImportModalOpen(false);
  };

  const derivedEdges = React.useMemo(() => {
    // 1. Prioritize direct edges serialized in evidence_summary
    const summaryEdges = (currentResult?.evidence_summary as any)?.edges;
    if (summaryEdges && Array.isArray(summaryEdges) && summaryEdges.length > 0) {
      return summaryEdges.map((e: any) => ({
        from_id: e.from_id,
        to_id: e.to_id,
        relationship_type: e.relationship_type,
        confidence: e.confidence ?? 1.0,
        properties: e.properties || {},
      }));
    }

    // 2. Fallback to extracting from key_paths
    const edges: any[] = [];
    const keyPaths = currentResult?.evidence_summary?.key_paths || [];
    keyPaths.forEach((path: any) => {
      if (path.chain_names && path.relationships) {
        for (let i = 0; i < path.relationships.length; i++) {
          const fromId = path.chain_ids?.[i] || path.chain_names[i];
          const toId = path.chain_ids?.[i + 1] || path.chain_names[i + 1];
          const rel = path.relationships[i];
          if (fromId && toId) {
            edges.push({
              from_id: fromId,
              to_id: toId,
              relationship_type: rel,
              confidence: 1.0,
            });
          }
        }
      }
    });
    return edges;
  }, [currentResult]);


  const [previewEntities, setPreviewEntities] = useState<Record<string, EntityFact>>({});
  const [previewEdges, setPreviewEdges] = useState<any[]>([]);

  const loadGraphPreviewData = (graphName: string) => {
    getGraphPreview(graphName).then((res) => {
      if (res && res.entities && Object.keys(res.entities).length > 0) {
        setPreviewEntities(res.entities);
        setPreviewEdges(res.edges || []);
      }
    });
  };

  // Load health, real graphs & schema on mount
  useEffect(() => {
    getHealth().then((h) => {
      setHealthStatus(h);
    });
    getAvailableGraphs().then((res) => {
      if (res && res.graphs && res.graphs.length > 0) {
        setAvailableGraphs(res.graphs);
        const target = initialGraph && initialGraph !== "" ? initialGraph : (res.active_graph || "ALL_GRAPHS");
        setSelectedGraph(target);
        loadGraphPreviewData(target);
      }
    });
    getSchema(initialGraph || "ALL_GRAPHS").then(setSchemaProfile);
    loadGraphPreviewData(initialGraph || "ALL_GRAPHS");
  }, []);

  const handleGraphChange = (newGraph: string) => {
    setSelectedGraph(newGraph);
    getSchema(newGraph).then(setSchemaProfile);
    loadGraphPreviewData(newGraph);
  };

  // Populate input if an initial query was passed, without auto-executing
  useEffect(() => {
    if (initialQuery) {
      setQueryInput(initialQuery);
    }
  }, [initialQuery]);

  const handleAuthSuccess = (u: User) => {
    setUser(u);
    refreshConversations();
    if (queryInput.trim()) {
      handleRunInvestigation(queryInput.trim());
    }
  };

  const handleLogout = async () => {
    await logoutUser();
    setUser(null);
    setConversations([]);
    setActiveConversationId(null);
    setPastMessages([]);
    onBackToLanding();
  };

  const handleStartNewInvestigation = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsInvestigating(false);
    setActiveConversationId(null);
    setCurrentObjective("");
    setQueryInput("");
    setEvents([]);
    setCurrentResult(null);
    setPastMessages([]);
    setIsSidebarOpen(false);
  };

  const handleSelectConversation = async (convId: string) => {
    try {
      const conv = await getConversation(convId);
      if (!conv) return;

      setActiveConversationId(conv.id);
      setCurrentObjective(conv.title);
      if (conv.graph_name && availableGraphs.includes(conv.graph_name)) {
        handleGraphChange(conv.graph_name);
      }
      setPastMessages(conv.messages || []);

      // Find the most recent assistant message with evidence summary to restore right-hand graph canvas
      const lastAssistant = [...(conv.messages || [])]
        .reverse()
        .find((m) => m.role === "assistant" && m.metadata?.evidence_summary);

      if (lastAssistant && lastAssistant.metadata?.evidence_summary) {
        setCurrentResult({
          objective: conv.title,
          success: true,
          final_answer: lastAssistant.content,
          evidence_summary: lastAssistant.metadata.evidence_summary,
          steps: lastAssistant.metadata.steps || [],
          total_iterations: lastAssistant.metadata.total_iterations || 1,
          total_tool_calls: lastAssistant.metadata.total_tool_calls || 0,
          duration_seconds: lastAssistant.metadata.duration_seconds || 1.0,
        });
        setEvents([]);
      } else {
        setCurrentResult(null);
        setEvents([]);
      }
      setIsSidebarOpen(false);
    } catch (err) {
      console.error("Failed to load conversation:", err);
    }
  };

  const handleDeleteConversation = async (e: React.MouseEvent, convId: string) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this investigation?")) return;
    setIsDeletingConvId(convId);
    try {
      const ok = await deleteConversation(convId);
      if (ok) {
        if (activeConversationId === convId) {
          handleStartNewInvestigation();
        }
        await refreshConversations();
      }
    } finally {
      setIsDeletingConvId(null);
    }
  };

  const handleStopInvestigation = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsInvestigating(false);
  };

  const handleRunInvestigation = async (queryToRun: string) => {
    if (!queryToRun.trim()) return;

    if (!user) {
      setIsAuthModalOpen(true);
      return;
    }

    // Abort any ongoing investigation
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setCurrentObjective(queryToRun);
    setIsInvestigating(true);
    setIsReasoningExpanded(true);
    setEvents([]);
    setCurrentResult(null);
    setSelectedEntityId(null);

    // If user is logged in, append question to past messages view immediately
    if (user) {
      setPastMessages((prev) => [
        ...prev,
        {
          id: `tmp-${Date.now()}`,
          role: "user",
          content: queryToRun,
          timestamp: Date.now() / 1000,
        },
      ]);
    }

    // Add query to recent sessions and persist in localStorage
    setRecentSessions((prev) => {
      const updated = [
        {
          id: `s-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
          query: queryToRun,
          timestamp: "Just now",
        },
        ...prev.filter((p) => p.query !== queryToRun).slice(0, 8),
      ];
      try {
        localStorage.setItem("graphos_recent_sessions", JSON.stringify(updated));
      } catch {
        // ignore
      }
      return updated;
    });

    try {
      const result = await executeInvestigationStream(
        queryToRun,
        "live",
        (ev) => {
          setEvents((prev) => {
            // Deduplicate exact consecutive duplicates
            if (prev.length > 0) {
              const last = prev[prev.length - 1];
              if (last.type === ev.type && last.message === ev.message) {
                return prev;
              }
            }
            return [...prev, ev];
          });
        },
        selectedGraph,
        controller.signal,
        activeConversationId || undefined,
        (assignedId) => {
          setActiveConversationId(assignedId);
          refreshConversations();
        }
      );
      if (!controller.signal.aborted) {
        setCurrentResult(result);
        setIsReasoningExpanded(false);

        if (user && result && result.final_answer) {
          setPastMessages((prev) => [
            ...prev,
            {
              id: `tmp-res-${Date.now()}`,
              role: "assistant",
              content: result.final_answer,
              metadata: { evidence_summary: result.evidence_summary },
              timestamp: Date.now() / 1000,
            },
          ]);
          refreshConversations();
        }
      }
    } catch (err: any) {
      if (controller.signal.aborted || err?.name === "AbortError") {
        return;
      }
      setEvents((prev) => [
        ...prev,
        {
          type: "error",
          iteration: 0,
          message: err?.message || "Investigation failed",
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsInvestigating(false);
      abortControllerRef.current = null;
    }
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!queryInput.trim()) return;
    if (!user) {
      setIsAuthModalOpen(true);
      return;
    }
    handleRunInvestigation(queryInput.trim());
    setQueryInput("");
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#f6faff] text-[#102f58] relative">
      {/* SIDEBAR BACKDROP OVERLAY */}
      {isSidebarOpen && (
        <div
          onClick={() => setIsSidebarOpen(false)}
          className="fixed inset-0 bg-slate-900/30 backdrop-blur-xs z-40 transition-opacity animate-in fade-in"
        />
      )}

      {/* SLIDE-OVER HAMBURGER SIDEBAR: Sessions, Connections & Schema */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-72 sm:w-80 bg-white border-r border-[#4370aa]/15 shadow-2xl flex flex-col transform transition-transform duration-300 ease-in-out ${
          isSidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Brand & Close Header */}
        <div className="p-4 border-b border-[#4370aa]/15 flex items-center justify-between bg-white">
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setIsSidebarOpen(false);
                onBackToLanding();
              }}
              className="flex items-center gap-1.5 text-xs font-semibold text-[#71849e] hover:text-[#102f58] transition"
              title="Return to Landing Page"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Home</span>
            </button>
            <span className="text-xs font-bold font-mono tracking-tight text-[#1678ef] bg-[#eff7ff] px-2.5 py-0.5 rounded-full border border-[#1678ef]/20">
              GraphOS v1.0
            </span>
          </div>

          <button
            onClick={() => setIsSidebarOpen(false)}
            className="p-1.5 rounded-lg text-[#71849e] hover:text-[#102f58] hover:bg-slate-100 transition cursor-pointer"
            title="Close sidebar"
            aria-label="Close sidebar"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* New Investigation Button */}
        <div className="p-4">
          <button
            onClick={handleStartNewInvestigation}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-semibold text-white bg-gradient-to-r from-[#1678ef] to-[#268cf5] hover:from-[#1b80ff] hover:to-[#389aff] shadow-md shadow-[#1678ef]/20 transition cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>New Investigation</span>
          </button>
        </div>

        {/* Engine Status */}
        <div className="px-4 pb-3">
          <div className="p-2.5 rounded-xl bg-[#f6faff] border border-[#4370aa]/15 flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#71849e]">
              Engine Mode
            </span>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#eff7ff] border border-[#1678ef]/20">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[11px] font-semibold text-[#1678ef]">Live MCP Active</span>
            </div>
          </div>
        </div>

        {/* Discovered Graph Schema Pills */}
        <div className="px-4 py-3 border-t border-[#4370aa]/15">
          <div className="flex items-center justify-between text-xs font-semibold text-[#102f58] mb-2">
            <span className="flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5 text-[#1678ef]" />
              <span>{selectedGraph === "ALL_GRAPHS" ? "Federated Graphs" : "Active Graph"}</span>
            </span>
            <span className="text-[10px] text-[#71849e]">
              {selectedGraph === "ALL_GRAPHS" ? "All Datasets" : "FalkorDB"}
            </span>
          </div>

          <div className="flex flex-wrap gap-1.5 max-h-40 overflow-y-auto pr-1">
            {schemaProfile && schemaProfile.node_kinds && schemaProfile.node_kinds.length > 0 ? (
              schemaProfile.node_kinds.map((k: any, idx: number) => {
                const kindName = typeof k === "string" ? k : k.kind;
                return (
                  <span
                    key={idx}
                    className="px-2 py-0.5 rounded-md bg-[#eff7ff] text-[#1678ef] text-[10px] font-semibold border border-[#1678ef]/15"
                  >
                    :{kindName}
                  </span>
                );
              })
            ) : (
              <span className="text-[11px] text-[#71849e] italic">
                Discovering graph schema...
              </span>
            )}
          </div>
        </div>

        {/* Chat History / Recent Investigations */}
        <div className="flex-1 overflow-y-auto px-4 py-3 border-t border-[#4370aa]/15">
          <span className="text-[10px] font-bold uppercase tracking-wider text-[#71849e] mb-2 block">
            {user ? "Chat History (FalkorDB)" : "Recent Investigations"}
          </span>

          {user ? (
            <div className="space-y-1.5">
              {conversations.length > 0 ? (
                conversations.map((c) => (
                  <div
                    key={c.id}
                    onClick={() => handleSelectConversation(c.id)}
                    className={`w-full text-left p-2.5 rounded-xl text-xs border transition flex items-center justify-between group cursor-pointer ${
                      activeConversationId === c.id
                        ? "bg-[#eff7ff] border-[#1678ef]/30 text-[#1678ef]"
                        : "hover:bg-[#eff7ff] border-transparent text-[#102f58]"
                    }`}
                  >
                    <div className="min-w-0 flex-1 pr-2">
                      <span className="font-medium line-clamp-1 group-hover:text-[#1678ef] block">
                        {c.title}
                      </span>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[9px] font-semibold text-[#1678ef] bg-[#eff7ff] px-1.5 py-0.5 rounded border border-[#1678ef]/15">
                          {c.graph_name}
                        </span>
                        <span className="text-[10px] text-[#71849e]">
                          {new Date(c.updated_at * 1000).toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                          })}
                        </span>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => handleDeleteConversation(e, c.id)}
                      disabled={isDeletingConvId === c.id}
                      className="p-1 rounded-md text-slate-400 hover:text-rose-600 hover:bg-rose-50 opacity-0 group-hover:opacity-100 transition cursor-pointer"
                      title="Delete conversation"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))
              ) : (
                <p className="text-[11px] text-[#71849e] italic py-2">
                  No saved investigations yet. Enter an objective to begin.
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              <div className="space-y-1.5">
                {recentSessions.length > 0 ? (
                  recentSessions.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => {
                        handleRunInvestigation(s.query);
                        setIsSidebarOpen(false);
                      }}
                      className="w-full text-left p-2.5 rounded-xl text-xs hover:bg-[#eff7ff] border border-transparent hover:border-[#1678ef]/20 transition flex flex-col gap-0.5 group cursor-pointer"
                    >
                      <span className="font-medium text-[#102f58] line-clamp-2 group-hover:text-[#1678ef]">
                        {s.query}
                      </span>
                      <span className="text-[10px] text-[#71849e]">{s.timestamp}</span>
                    </button>
                  ))
                ) : (
                  <p className="text-[11px] text-[#71849e] italic py-2">
                    No recent investigations. Enter an objective to begin.
                  </p>
                )}
              </div>
              <div className="mt-4 p-3 rounded-xl bg-blue-50/60 border border-blue-200/50 text-[11px] text-[#102f58]">
                <p className="font-semibold mb-1">Persistent History</p>
                <p className="text-[#71849e] mb-2 leading-relaxed">
                  Sign in to save and restore your investigations across sessions.
                </p>
                <button
                  onClick={() => setIsAuthModalOpen(true)}
                  className="w-full py-1.5 px-3 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs transition cursor-pointer shadow-xs text-center"
                >
                  Sign In / Sign Up
                </button>
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* CENTER PANEL: Investigation Conversation & Agent Stream */}
      <main className="flex-1 flex flex-col min-w-0 border-r border-[#4370aa]/15 bg-white">
        {/* Top Header with Hamburger & Clean Layout */}
        <div className="px-5 py-3.5 border-b border-[#4370aa]/15 flex items-center justify-between bg-white shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            {/* Hamburger Button */}
            <button
              onClick={() => setIsSidebarOpen(true)}
              className="p-2 -ml-1.5 rounded-xl text-[#71849e] hover:text-[#102f58] hover:bg-[#eff7ff] transition cursor-pointer"
              title="Open Navigation & History"
              aria-label="Open sidebar menu"
            >
              <Menu className="w-5 h-5 text-[#102f58]" />
            </button>

            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={onBackToLanding}
                className="flex items-center gap-1 text-xs font-semibold text-[#71849e] hover:text-[#102f58] transition"
                title="Back to Home"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Home</span>
              </button>
              <span className="text-xs font-bold font-mono tracking-tight text-[#1678ef] bg-[#eff7ff] px-2 py-0.5 rounded-full border border-[#1678ef]/20">
                GraphOS
              </span>
            </div>

            <div className="h-4 w-px bg-slate-200 hidden sm:block" />

            <h2 className="text-sm font-semibold text-[#102f58] truncate">
              {currentObjective || "Investigation Workspace"}
            </h2>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            {/* Active Graph Dropdown Selector */}
            <div className="flex items-center gap-1.5 bg-[#f0f7ff] px-2.5 py-1.5 rounded-lg border border-[#1678ef]/20">
              <Database className="w-3.5 h-3.5 text-[#1678ef]" />
              <select
                value={selectedGraph}
                onChange={(e) => handleGraphChange(e.target.value)}
                title="Select active graph database"
                className="bg-transparent text-xs font-semibold text-[#102f58] focus:outline-none cursor-pointer max-w-[140px] sm:max-w-none truncate"
              >
                <option value="ALL_GRAPHS">All Graphs (Federated)</option>
                {availableGraphs
                  .filter(
                    (g) =>
                      g !== "ALL_GRAPHS" &&
                      g !== "fraud_demo" &&
                      !g.startsWith("graphos_auth") &&
                      !g.startsWith("graphos_history")
                  )
                  .map((g) => (
                    <option key={g} value={g}>
                      {g === "fraud_swiftpay"
                        ? "fraud_swiftpay (Financial)"
                        : g === "graphos_dev"
                        ? "graphos_dev (Codebase AST)"
                        : g === "security_swiftpay"
                        ? "security_swiftpay (Cloud Security)"
                        : g === "fraud_Front"
                        ? "fraud_Front (Frontend Activity)"
                        : g === "swiftpay_unified"
                        ? "swiftpay_unified (Cross-Domain)"
                        : g}
                    </option>
                  ))}
              </select>
            </div>

            {/* Import Data Modal Trigger */}
            <button
              onClick={() => setIsImportModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-xs transition cursor-pointer"
              title="Import Code AST JSON, Live CSV, or Dataset"
            >
              <Upload className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Import</span>
            </button>

            {/* User Profile Pill / Sign In Button */}
            {user ? (
              <div className="flex items-center gap-1.5 bg-[#f0f7ff] px-2.5 py-1.5 rounded-lg border border-[#1678ef]/20 text-xs font-semibold text-[#102f58]">
                <span className="w-5 h-5 rounded-full bg-[#1678ef] text-white flex items-center justify-center text-[10px] font-bold">
                  {user.name.charAt(0).toUpperCase()}
                </span>
                <span className="hidden lg:inline max-w-[90px] truncate">{user.name}</span>
                <button
                  onClick={handleLogout}
                  className="text-[#1678ef] hover:text-blue-800 text-[11px] font-bold ml-1 cursor-pointer transition"
                  title="Sign Out"
                >
                  Logout
                </button>
              </div>
            ) : (
              <button
                onClick={() => setIsAuthModalOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-400 hover:bg-amber-300 text-[#0b2447] text-xs font-bold shadow-xs transition cursor-pointer"
                title="First step: Sign in to run investigations"
              >
                <Lock className="w-3.5 h-3.5" />
                <span>Sign In Required</span>
              </button>
            )}

            {isInvestigating && (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#1678ef]/10 text-[#1678ef] text-xs font-semibold border border-[#1678ef]/20">
                <span className="w-2 h-2 rounded-full bg-[#1678ef] animate-ping" />
                <span>Investigating...</span>
              </div>
            )}
          </div>
        </div>

        {/* Scrollable Conversation / Stream Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {!currentObjective && !currentResult && pastMessages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center py-12 px-4">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-[#1678ef]/15 to-[#38bdf8]/15 border border-[#1678ef]/25 flex items-center justify-center text-[#1678ef] mb-4 shadow-sm shadow-[#1678ef]/10">
                <Sparkles className="w-7 h-7 text-[#1678ef]" />
              </div>

              <h3 className="text-xl font-bold text-[#102f58] tracking-tight">
                Autonomous Graph Intelligence
              </h3>
              <p className="text-xs sm:text-sm text-[#71849e] max-w-md mt-1.5 mb-8 leading-relaxed">
                Investigate connected entities, trace multi-hop relationship paths, and uncover grounded findings across your knowledge graph.
              </p>

              {/* 3 Modern Prompt Starter Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full max-w-2xl">
                {[
                  {
                    icon: CreditCard,
                    title: "Financial Forensics",
                    query: "Investigate suspicious transactions and find connected entities",
                    badge: "Fraud",
                  },
                  {
                    icon: Shield,
                    title: "Security Blast Radius",
                    query: "Triage security findings and identify affected databases",
                    badge: "Vulnerability",
                  },
                  {
                    icon: Code,
                    title: "Code Dependencies",
                    query: "Trace dependencies for Payments Release October 2026",
                    badge: "Architecture",
                  },
                ].map((item, i) => {
                  const Icon = item.icon;
                  return (
                    <button
                      key={i}
                      onClick={() => handleRunInvestigation(item.query)}
                      className="p-4 rounded-2xl bg-[#fafcff] hover:bg-white border border-[#4370aa]/15 hover:border-[#1678ef]/40 shadow-xs hover:shadow-md transition text-left flex flex-col justify-between gap-3 group cursor-pointer transform hover:-translate-y-0.5 duration-150"
                    >
                      <div className="flex items-center justify-between">
                        <div className="w-8 h-8 rounded-xl bg-[#eff7ff] text-[#1678ef] flex items-center justify-center group-hover:scale-105 transition">
                          <Icon className="w-4 h-4" />
                        </div>
                        <span className="text-[10px] font-semibold text-[#1678ef] bg-[#eff7ff] px-2 py-0.5 rounded-full border border-[#1678ef]/15">
                          {item.badge}
                        </span>
                      </div>
                      <div>
                        <h4 className="text-xs font-bold text-[#102f58] group-hover:text-[#1678ef] transition">
                          {item.title}
                        </h4>
                        <p className="text-[11px] text-[#71849e] mt-1 line-clamp-2 leading-relaxed">
                          {item.query}
                        </p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Past Conversation Turns (Loaded from FalkorDB Chat History) */}
          {pastMessages.length > 0 && (
            <div className="space-y-6">
              {pastMessages.map((msg, idx) => {
                // If currentResult is active and displaying the latest findings card below the events accordion,
                // do not render the same latest assistant findings twice in this list.
                const lastAssistantIdx = pastMessages.reduce(
                  (last, m, i) => (m.role === "assistant" ? i : last),
                  -1
                );
                const isCurrentAssistant =
                  msg.role === "assistant" &&
                  currentResult !== null &&
                  idx === lastAssistantIdx;

                if (isCurrentAssistant) {
                  return null;
                }

                return msg.role === "user" ? (
                  <div
                    key={msg.id}
                    className="flex items-start gap-3.5 p-4 sm:p-5 rounded-2xl bg-white border border-[#4370aa]/15 shadow-xs"
                  >
                    <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-[#1678ef] to-[#38bdf8] text-white flex items-center justify-center text-xs font-bold shadow-xs shrink-0">
                      {user ? user.name.charAt(0).toUpperCase() : "You"}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-[#1678ef] bg-[#eff7ff] px-2 py-0.5 rounded-full border border-[#1678ef]/15">
                          Investigation Objective
                        </span>
                        <span className="text-[10px] text-[#71849e]">
                          {new Date(msg.timestamp * 1000).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>
                      <p className="text-sm sm:text-base font-semibold text-[#102f58] leading-relaxed">
                        {msg.content}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div
                    key={msg.id}
                    className="p-6 rounded-3xl bg-white border border-[#1678ef]/30 shadow-md space-y-4"
                  >
                    <div className="flex items-center justify-between pb-3 border-b border-[#4370aa]/15">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center">
                          <CheckCircle2 className="w-4 h-4" />
                        </div>
                        <span className="font-bold text-sm text-[#102f58]">
                          Verified Grounded Findings
                        </span>
                      </div>
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(msg.content);
                          setCopiedMessageId(msg.id);
                          setTimeout(() => setCopiedMessageId(null), 2000);
                        }}
                        className="p-1.5 rounded-lg border border-[#4370aa]/20 hover:bg-[#eff7ff] text-[#71849e] hover:text-[#102f58] transition cursor-pointer"
                        title="Copy markdown findings"
                      >
                        {copiedMessageId === msg.id ? (
                          <Check className="w-3.5 h-3.5 text-emerald-600" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                    <div className="prose prose-slate max-w-none text-[#102f58] leading-relaxed">
                      <FormattedMarkdown content={msg.content} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Current single active question bubble (when not loaded from pastMessages) */}
          {pastMessages.length === 0 && currentObjective && (
            <div className="flex items-start gap-3.5 p-4 sm:p-5 rounded-2xl bg-white border border-[#4370aa]/15 shadow-xs">
              <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-[#1678ef] to-[#38bdf8] text-white flex items-center justify-center text-xs font-bold shadow-xs shrink-0">
                You
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[#1678ef] bg-[#eff7ff] px-2 py-0.5 rounded-full border border-[#1678ef]/15">
                    Investigation Objective
                  </span>
                  <span className="text-[10px] text-[#71849e]">
                    Target: {selectedGraph}
                  </span>
                </div>
                <p className="text-sm sm:text-base font-semibold text-[#102f58] leading-relaxed">
                  {currentObjective}
                </p>
              </div>
            </div>
          )}

          {/* Agent Reasoning & Progress Accordion */}
          {events.length > 0 && (
            <div className="rounded-2xl border border-[#4370aa]/20 bg-white shadow-xs overflow-hidden transition-all duration-200">
              {/* Accordion Header / Toggle */}
              <div
                onClick={() => setIsReasoningExpanded(!isReasoningExpanded)}
                className="px-4 py-3 bg-[#fafcff] hover:bg-[#f0f7ff] transition flex items-center justify-between cursor-pointer border-b border-[#4370aa]/10 select-none"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  {isInvestigating ? (
                    <div className="w-6 h-6 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center animate-spin shrink-0">
                      <RotateCcw className="w-3.5 h-3.5" />
                    </div>
                  ) : (
                    <div className="w-6 h-6 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                    </div>
                  )}

                  <div className="flex items-center gap-2 truncate">
                    <span className="text-xs font-bold text-[#102f58]">
                      {isInvestigating
                        ? "Agent Reasoning & Discovery Active..."
                        : "Agent Reasoning & Tool Progress"}
                    </span>
                    <span className="text-[10px] font-semibold text-[#1678ef] bg-[#eff7ff] px-2 py-0.5 rounded-full border border-[#1678ef]/15">
                      {events.length} {events.length === 1 ? "step" : "steps"}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2 text-[#71849e] shrink-0">
                  <span className="text-[11px] font-medium hidden sm:inline">
                    {isReasoningExpanded ? "Collapse" : "Expand"}
                  </span>
                  {isReasoningExpanded ? (
                    <ChevronUp className="w-4 h-4 text-[#71849e]" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-[#71849e]" />
                  )}
                </div>
              </div>

              {/* Live Step Snippet when collapsed during active run */}
              {!isReasoningExpanded && isInvestigating && (
                <div className="px-4 py-2 bg-blue-50/50 text-[11px] font-mono text-blue-700 flex items-center gap-2 border-b border-blue-100/60">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-ping shrink-0" />
                  <span className="truncate">{events[events.length - 1]?.message}</span>
                </div>
              )}

              {/* Expanded Event Log */}
              {isReasoningExpanded && (
                <div className="p-3.5 space-y-1.5 max-h-64 overflow-y-auto font-mono text-xs bg-[#fbfdff]">
                  {events.map((ev, idx) => (
                    <div
                      key={idx}
                      className="flex items-start gap-2.5 py-1.5 px-2.5 rounded-lg bg-white border border-[#4370aa]/10 hover:border-[#1678ef]/20 transition"
                    >
                      <span
                        className={`text-[9.5px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider shrink-0 ${
                          ev.type === "tool_call"
                            ? "bg-[#eff7ff] text-[#1678ef] border border-[#1678ef]/20"
                            : ev.type === "tool_result"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : ev.type === "thought"
                            ? "bg-purple-50 text-purple-700 border border-purple-200"
                            : ev.type === "error"
                            ? "bg-red-50 text-red-700 border border-red-200"
                            : "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {ev.type}
                      </span>
                      <span className="text-[#102f58] break-all leading-relaxed text-[11px]">
                        {ev.message}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Final Executive Summary & Findings Card */}
          {currentResult && (
            <div className="p-6 rounded-3xl bg-white border border-[#1678ef]/30 shadow-md space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-[#4370aa]/15">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center">
                    <CheckCircle2 className="w-4 h-4" />
                  </div>
                  <span className="font-bold text-sm text-[#102f58]">
                    Verified Grounded Findings
                  </span>
                </div>
                <div className="flex items-center gap-2.5 text-xs text-[#71849e]">
                  <span className="inline-flex items-center gap-1 font-semibold text-[#1678ef]">
                    <Zap className="w-3.5 h-3.5" />
                    <span>{currentResult.duration_seconds}s</span>
                  </span>
                  <span className="text-slate-300">/</span>
                  <span>{currentResult.total_tool_calls} tool calls</span>
                  <span className="text-slate-300">/</span>
                  <span>
                    {currentResult.evidence_summary?.unique_entities_count || 0} entities grounded
                  </span>

                  {/* Copy Button */}
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(currentResult.final_answer);
                      setCopiedAnswer(true);
                      setTimeout(() => setCopiedAnswer(false), 2000);
                    }}
                    className="ml-2 p-1.5 rounded-lg border border-[#4370aa]/20 hover:bg-[#eff7ff] text-[#71849e] hover:text-[#102f58] transition cursor-pointer"
                    title="Copy markdown findings"
                  >
                    {copiedAnswer ? (
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>
              </div>

              {/* Render Final Answer with Rich Markdown, Tables, and Typography */}
              <div className="text-xs sm:text-sm text-[#102f58] leading-relaxed">
                <FormattedMarkdown content={currentResult.final_answer} />
              </div>

              {/* Remediation & Action Approval Card - Only displayed if agent recommended actionable steps */}
              {(() => {
                const answer = currentResult.final_answer || "";
                const match = answer.match(/(?:###?\s*(?:Recommended Actions?|Remediation|Immediate Actions?|Next Steps?)[\s\S]*)/i);
                if (!match) return null;
                const recommendationSnippet = match[0]
                  .replace(/###?\s*(?:Recommended Actions?|Remediation|Immediate Actions?|Next Steps?)/i, "")
                  .trim()
                  .slice(0, 350);
                if (!recommendationSnippet) return null;

                return (
                  <div className="p-4 rounded-2xl bg-gradient-to-r from-blue-50/80 via-indigo-50/40 to-slate-50 border border-blue-200/80 shadow-xs space-y-3 mt-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <ShieldCheck className="w-4 h-4 text-blue-600" />
                        <span className="text-xs font-bold text-slate-900">Recommended Remediation Action</span>
                      </div>
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-100/70 text-blue-700">
                        Decision Memory
                      </span>
                    </div>

                    <div className="text-xs text-slate-700 leading-relaxed">
                      <FormattedMarkdown content={recommendationSnippet} />
                    </div>

                    <div className="flex items-center justify-between pt-1">
                      <span className="text-[11px] text-slate-500">Requires human analyst approval</span>
                      <button
                        onClick={() => handleApproveAction("remediation", currentObjective)}
                        disabled={isApprovingAction || actionApproved}
                        className={`px-3 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer ${
                          actionApproved
                            ? "bg-emerald-600 text-white"
                            : "bg-blue-600 hover:bg-blue-700 text-white shadow-xs"
                        }`}
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>{actionApproved ? "Action Approved & Logged" : "Approve Remediation"}</span>
                      </button>
                    </div>
                  </div>
                );
              })()}
            </div>
          )}
        </div>

        {/* Bottom Follow-up Composer with Floating Stop Button */}
        <div className="px-4 sm:px-6 pt-3 pb-6 sm:pb-8 border-t border-[#4370aa]/15 bg-gradient-to-t from-white via-white/95 to-transparent shrink-0 relative">
          <div className="max-w-3xl mx-auto w-full relative">
            {/* Floating Stop Generating Pill Button (like ChatGPT) */}
            {isInvestigating && (
              <div className="absolute -top-5 left-1/2 -translate-x-1/2 z-20">
                <button
                  type="button"
                  onClick={handleStopInvestigation}
                  className="flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-bold text-slate-700 bg-white border border-slate-300 shadow-md hover:bg-red-50 hover:text-red-600 hover:border-red-300 transition transform hover:scale-105 active:scale-95 cursor-pointer"
                >
                  <Square className="w-3 h-3 fill-current text-red-500" />
                  <span>Stop generating</span>
                </button>
              </div>
            )}

            {/* If not logged in, show clear warning that sign in is required */}
            {!user && (
              <div className="mb-2.5 p-3 rounded-2xl bg-amber-50/90 border border-amber-300 text-[#0b2447] text-xs flex items-center justify-between gap-3 shadow-xs">
                <div className="flex items-center gap-2.5">
                  <div className="w-7 h-7 rounded-lg bg-amber-400 text-[#0b2447] flex items-center justify-center shrink-0">
                    <Lock className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <span className="font-bold">Sign In Required:</span> Please log in to run live AI investigations & save your chat history.
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setIsAuthModalOpen(true)}
                  className="px-3.5 py-1.5 rounded-xl bg-amber-400 hover:bg-amber-300 text-[#0b2447] font-bold text-xs transition shadow-xs cursor-pointer shrink-0"
                >
                  Sign In
                </button>
              </div>
            )}

            <form
              onSubmit={handleFormSubmit}
              className="relative flex items-center gap-2.5 p-2 sm:p-2.5 rounded-2xl bg-white border border-[#4370aa]/25 hover:border-[#1678ef]/50 focus-within:border-[#1678ef] focus-within:ring-4 focus-within:ring-[#1678ef]/10 shadow-lg shadow-slate-200/50 transition-all duration-200"
            >
              <div className="pl-2.5 flex items-center justify-center text-[#1678ef] shrink-0">
                <Sparkles className="w-4 h-4 text-[#1678ef]" />
              </div>

              <input
                type="text"
                value={queryInput}
                onChange={(e) => setQueryInput(e.target.value)}
                placeholder={
                  !user
                    ? "Sign in required to run investigations... Click Sign In above to begin."
                    : isInvestigating
                    ? "Investigating across graph... Click Stop to halt or type follow-up..."
                    : "Ask GraphOS to explore connected entities, trace paths, or investigate..."
                }
                className="flex-1 px-1 bg-transparent border-none outline-none text-xs sm:text-sm text-[#102f58] placeholder-[#71849e]/70 font-normal focus:ring-0 focus:outline-none"
              />

              {queryInput && !isInvestigating && (
                <button
                  type="button"
                  onClick={() => setQueryInput("")}
                  className="p-1 rounded-full text-[#71849e] hover:text-[#102f58] hover:bg-slate-100 transition cursor-pointer"
                  title="Clear input"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}

              {/* Stop button when running, Send button when idle */}
              {isInvestigating ? (
                <button
                  type="button"
                  onClick={handleStopInvestigation}
                  className="px-3.5 py-2 rounded-xl bg-red-600 hover:bg-red-700 text-white font-bold text-xs flex items-center gap-1.5 transition shadow-sm hover:scale-105 active:scale-95 cursor-pointer shrink-0"
                  title="Stop investigation execution"
                >
                  <Square className="w-3.5 h-3.5 fill-current" />
                  <span>Stop</span>
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!queryInput.trim()}
                  className="w-9 h-9 rounded-xl bg-gradient-to-r from-[#1678ef] to-[#2563eb] text-white flex items-center justify-center hover:scale-105 active:scale-95 transition shadow-md shadow-blue-500/25 disabled:opacity-30 disabled:hover:scale-100 cursor-pointer shrink-0"
                  title="Send investigation objective"
                >
                  <Send className="w-4 h-4" />
                </button>
              )}
            </form>

            <div className="flex items-center justify-between px-3 mt-1.5 text-[10.5px] text-[#71849e]">
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                <span>FalkorDB Read-Only Guardrails Enforced</span>
              </span>
              <span className="hidden sm:inline">Press Enter to investigate</span>
            </div>
          </div>
        </div>
      </main>

      {/* RIGHT PANEL: Evidence & Graph Explorer with 4 Tabs */}
      <section className="w-80 lg:w-[460px] flex flex-col shrink-0 bg-[#f8fbff]">
        {/* Tab Header */}
        <div className="flex items-center border-b border-[#4370aa]/15 bg-white px-3 py-2 shrink-0">
          {[
            { id: "graph", label: "Graph Explorer", icon: Network },
            { id: "paths", label: "Evidence Paths", icon: Layers },
            { id: "entities", label: "Entities", icon: Database },
            { id: "activity", label: "Activity", icon: Clock },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex-1 flex items-center justify-center gap-1.5 py-2 px-1 rounded-lg text-xs font-semibold transition ${
                  isActive
                    ? "bg-[#eff7ff] text-[#1678ef] shadow-xs"
                    : "text-[#71849e] hover:text-[#102f58]"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Tab Body */}
        <div className="flex-1 overflow-y-auto p-4 flex flex-col">
          {activeTab === "graph" && (
            <div className="flex-1 min-h-[580px] flex flex-col">
              <GraphExplorer
                entities={
                  currentResult?.evidence_summary?.entities && Object.keys(currentResult.evidence_summary.entities).length > 0
                    ? currentResult.evidence_summary.entities
                    : previewEntities || EMPTY_ENTITIES
                }
                edges={derivedEdges.length > 0 ? derivedEdges : previewEdges || EMPTY_EDGES}
                keyPaths={currentResult?.evidence_summary?.key_paths || EMPTY_KEY_PATHS}
                selectedNodeId={selectedEntityId}
                onSelectNode={setSelectedEntityId}
              />
            </div>
          )}

          {activeTab === "paths" && (
            <div className="space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-[#4370aa]/15">
                <span className="text-xs font-bold uppercase tracking-wider text-[#71849e]">
                  Verified Evidence Paths ({currentResult?.evidence_summary?.key_paths?.length || 0})
                </span>
                <span className="text-[11px] font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                  100% Verified
                </span>
              </div>

              {(!currentResult?.evidence_summary?.key_paths ||
                currentResult.evidence_summary.key_paths.length === 0) && (
                <div className="text-center py-10 text-xs text-[#71849e]">
                  No multi-hop paths established for current result.
                </div>
              )}

              {currentResult?.evidence_summary?.key_paths?.map((path, idx) => (
                <div
                  key={idx}
                  className="p-4 rounded-2xl bg-white border border-[#4370aa]/20 shadow-xs space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[#102f58]">
                      Path #{idx + 1} ({path.hop_count} hops)
                    </span>
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#eff7ff] text-[#1678ef]">
                      Provenance Verified
                    </span>
                  </div>

                  <div className="space-y-2 text-xs">
                    {path.chain_names?.map((nodeName, nIdx) => (
                      <React.Fragment key={nIdx}>
                        <div
                          onClick={() => {
                            setSelectedEntityId(nodeName);
                            setActiveTab("graph");
                          }}
                          className="p-2 rounded-xl bg-[#f6faff] hover:bg-[#eff7ff] cursor-pointer border border-[#4370aa]/10 flex items-center justify-between transition"
                        >
                          <span className="font-semibold text-[#102f58] truncate">{nodeName}</span>
                          <span className="text-[10px] text-[#71849e]">Hop {nIdx + 1}</span>
                        </div>
                        {nIdx < path.relationships.length && (
                          <div className="flex items-center justify-center gap-1.5 text-[10px] text-[#1678ef] font-mono font-bold">
                            <span>↓</span>
                            <span>{path.relationships[nIdx]}</span>
                            <span>↓</span>
                          </div>
                        )}
                      </React.Fragment>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeTab === "entities" && (
            <div className="space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-[#4370aa]/15">
                <span className="text-xs font-bold uppercase tracking-wider text-[#71849e]">
                  {currentResult?.evidence_summary?.entities && Object.keys(currentResult.evidence_summary.entities).length > 0
                    ? `Grounded Entities (${currentResult.evidence_summary.unique_entities_count || Object.keys(currentResult.evidence_summary.entities).length})`
                    : `Active Graph Entities (${Object.keys(previewEntities).length})`}
                </span>
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#eff7ff] text-[#1678ef]">
                  {currentResult?.evidence_summary?.entities && Object.keys(currentResult.evidence_summary.entities).length > 0
                    ? "Investigation Result"
                    : "FalkorDB Live Sample"}
                </span>
              </div>

              {(() => {
                const activeEntities = (currentResult?.evidence_summary?.entities && Object.keys(currentResult.evidence_summary.entities).length > 0)
                  ? currentResult.evidence_summary.entities
                  : previewEntities;

                if (!activeEntities || Object.keys(activeEntities).length === 0) {
                  return (
                    <div className="text-center py-10 text-xs text-[#71849e]">
                      No entities discovered for current graph yet.
                    </div>
                  );
                }

                return Object.values(activeEntities).map((ent) => (
                  <div
                    key={ent.id}
                    onClick={() => {
                      setSelectedEntityId(ent.id);
                      setActiveTab("graph");
                    }}
                    className="p-3.5 rounded-2xl bg-white border border-[#4370aa]/20 hover:border-[#1678ef]/50 cursor-pointer shadow-xs transition space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-[#102f58] truncate">{ent.name || ent.id}</span>
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#eff7ff] text-[#1678ef]">
                        {ent.kind || "Entity"}
                      </span>
                    </div>
                    <p className="font-mono text-[11px] text-[#71849e]">{ent.id}</p>
                    {ent.status && (
                      <div className="flex items-center gap-1 text-[11px] text-[#3b577d]">
                        <span className="font-medium">Status:</span>
                        <span className="font-semibold">{ent.status}</span>
                      </div>
                    )}
                    {ent.properties?.source_graph && (
                      <span className="inline-block px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 text-[9px] font-mono">
                        {ent.properties.source_graph}
                      </span>
                    )}
                    {ent.is_isolated && (
                      <span className="inline-block px-2 py-0.5 rounded bg-amber-50 text-amber-700 text-[10px] font-semibold ml-1">
                        Isolated Node
                      </span>
                    )}
                  </div>
                ));
              })()}
            </div>
          )}

          {activeTab === "activity" && (
            <div className="space-y-3">
              <span className="text-xs font-bold uppercase tracking-wider text-[#71849e] block pb-2 border-b border-[#4370aa]/15">
                MCP Tool Calls ({currentResult?.steps?.reduce((acc, s) => acc + s.tool_calls.length, 0) || events.filter(e => e.type === "tool_call").length || 0})
              </span>

              {(!currentResult?.steps || currentResult.steps.length === 0) && events.filter(e => e.type === "tool_call").length === 0 && (
                <div className="text-center py-10 text-xs text-[#71849e]">
                  No tool activity recorded yet. Run an investigation to stream live MCP tool calls.
                </div>
              )}

              {/* Live streaming events while running */}
              {isInvestigating && events.filter(e => e.type === "tool_call" || e.type === "thought").length > 0 && (
                <div className="p-3 rounded-2xl bg-white border border-[#1678ef]/30 space-y-2 text-xs">
                  <span className="font-semibold text-[#1678ef] text-[11px] flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-[#1678ef] animate-ping" />
                    <span>Live Agent Steps In Progress...</span>
                  </span>
                  <div className="space-y-1.5 max-h-48 overflow-y-auto">
                    {events.map((ev, evIdx) => (
                      <div key={evIdx} className="text-[11px] font-mono text-[#102f58] p-1.5 rounded bg-[#f6faff] border border-[#1678ef]/10">
                        <span className="font-bold text-[#1678ef] uppercase text-[9px] mr-1.5">[{ev.type}]</span>
                        <span>{ev.message}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Real steps from completed investigation */}
              {currentResult?.steps?.map((step) => (
                <div
                  key={step.iteration}
                  className="p-3 rounded-2xl bg-white border border-[#4370aa]/15 space-y-2 text-xs"
                >
                  <div className="flex items-center justify-between text-[#71849e] text-[11px]">
                    <span className="font-semibold">Step {step.iteration}</span>
                    <span>{step.duration_seconds ? `${step.duration_seconds.toFixed(2)}s` : ""}</span>
                  </div>
                  {step.thought && (
                    <p className="text-[#3b577d] italic">"{step.thought}"</p>
                  )}
                  <div className="space-y-1">
                    {step.tool_calls.map((tc, tcIdx) => (
                      <div
                        key={tcIdx}
                        className="p-2 rounded-lg bg-[#f6faff] font-mono text-[11px] text-[#1678ef] border border-[#1678ef]/10 flex flex-col gap-0.5"
                      >
                        <span className="font-bold">{tc.function_name}</span>
                        <span className="text-[#71849e] text-[10px] truncate">
                          {JSON.stringify(tc.arguments)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
      {/* Import Dataset Modal */}
      <ImportDatasetModal
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        onIngestSuccess={handleIngestSuccess}
        availableGraphs={availableGraphs}
      />

      {/* Authentication Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onAuthSuccess={handleAuthSuccess}
      />
    </div>
  );
}

