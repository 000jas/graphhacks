"use client";

import React, { useState, useEffect } from "react";
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
} from "lucide-react";
import {
  InvestigationResult,
  InvestigationEvent,
  HealthStatus,
  GraphSchemaProfile,
  EntityFact,
} from "../types";
import { executeInvestigationStream, getHealth, getSchema } from "../lib/api";
import { GraphExplorer } from "./GraphExplorer";

interface WorkspaceProps {
  initialQuery?: string;
  initialMode?: "live" | "demo";
  onBackToLanding: () => void;
}

export function Workspace({
  initialQuery = "",
  initialMode = "live",
  onBackToLanding,
}: WorkspaceProps) {
  const [mode, setMode] = useState<"live" | "demo">(initialMode);
  const [queryInput, setQueryInput] = useState(initialQuery);
  const [currentObjective, setCurrentObjective] = useState(initialQuery);
  const [isInvestigating, setIsInvestigating] = useState(false);
  const [activeTab, setActiveTab] = useState<"graph" | "paths" | "entities" | "activity">("graph");
  const [events, setEvents] = useState<InvestigationEvent[]>([]);
  const [currentResult, setCurrentResult] = useState<InvestigationResult | null>(null);
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [recentSessions, setRecentSessions] = useState<
    Array<{ id: string; query: string; timestamp: string }>
  >([
    { id: "s-fraud", query: "Investigate suspicious transactions and find connected entities", timestamp: "Just now" },
    { id: "s-sec", query: "Triage security finding CVE-2026-4412 blast radius", timestamp: "10m ago" },
    { id: "s-code", query: "Find blockers for Payments Release October 2026", timestamp: "1h ago" },
  ]);
  const [schemaProfile, setSchemaProfile] = useState<GraphSchemaProfile | null>(null);
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);

  // Load health & schema on mount
  useEffect(() => {
    getHealth().then((h) => {
      setHealthStatus(h);
      if (!h) {
        // If live backend not reached, switch to demo mode with notice
        setMode("demo");
      }
    });
    getSchema().then(setSchemaProfile);
  }, []);

  // Run initial query if provided
  useEffect(() => {
    if (initialQuery) {
      handleRunInvestigation(initialQuery);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRunInvestigation = async (queryToRun: string) => {
    if (!queryToRun.trim() || isInvestigating) return;

    setCurrentObjective(queryToRun);
    setIsInvestigating(true);
    setEvents([]);
    setCurrentResult(null);
    setSelectedEntityId(null);

    // Add to recent sessions
    setRecentSessions((prev) => [
      { id: `s-${Date.now()}`, query: queryToRun, timestamp: "Just now" },
      ...prev.slice(0, 9),
    ]);

    try {
      const result = await executeInvestigationStream(queryToRun, mode, (ev) => {
        setEvents((prev) => [...prev, ev]);
      });
      setCurrentResult(result);
    } catch (err: any) {
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
    }
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!queryInput.trim()) return;
    handleRunInvestigation(queryInput.trim());
    setQueryInput("");
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#f6faff] text-[#102f58]">
      {/* LEFT SIDEBAR: Sessions, Connections & Schema */}
      <aside className="w-64 lg:w-72 border-r border-[#4370aa]/15 bg-white/80 backdrop-blur-md flex flex-col shrink-0">
        {/* Brand header */}
        <div className="p-4 border-b border-[#4370aa]/15 flex items-center justify-between">
          <button
            onClick={onBackToLanding}
            className="flex items-center gap-2 text-xs font-semibold text-[#71849e] hover:text-[#102f58] transition"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Home</span>
          </button>

          <span className="text-xs font-bold font-mono tracking-tight text-[#1678ef] bg-[#eff7ff] px-2.5 py-0.5 rounded-full border border-[#1678ef]/20">
            GraphOS v1.0
          </span>
        </div>

        {/* New Investigation Button */}
        <div className="p-4">
          <button
            onClick={() => {
              setCurrentResult(null);
              setEvents([]);
              setCurrentObjective("");
              setQueryInput("");
            }}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-semibold text-white bg-gradient-to-r from-[#1678ef] to-[#268cf5] hover:from-[#1b80ff] hover:to-[#389aff] shadow-md shadow-[#1678ef]/20 transition"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>New Investigation</span>
          </button>
        </div>

        {/* Mode Selector */}
        <div className="px-4 pb-3">
          <div className="p-2.5 rounded-xl bg-[#f6faff] border border-[#4370aa]/15 flex flex-col gap-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#71849e]">
              Engine Mode
            </span>
            <div className="flex items-center gap-1 bg-white p-0.5 rounded-lg border border-[#4370aa]/10">
              <button
                onClick={() => setMode("live")}
                className={`flex-1 py-1 px-2 rounded-md text-[11px] font-semibold transition ${
                  mode === "live"
                    ? "bg-[#1678ef] text-white shadow-sm"
                    : "text-[#71849e] hover:text-[#102f58]"
                }`}
              >
                Live MCP
              </button>
              <button
                onClick={() => setMode("demo")}
                className={`flex-1 py-1 px-2 rounded-md text-[11px] font-semibold transition ${
                  mode === "demo"
                    ? "bg-amber-500 text-white shadow-sm"
                    : "text-[#71849e] hover:text-[#102f58]"
                }`}
              >
                Demo Scenarios
              </button>
            </div>
          </div>
        </div>

        {/* Discovered Graph Schema Pills */}
        <div className="px-4 py-3 border-t border-[#4370aa]/15">
          <div className="flex items-center justify-between text-xs font-semibold text-[#102f58] mb-2">
            <span className="flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5 text-[#1678ef]" />
              <span>Active Graph</span>
            </span>
            <span className="text-[10px] text-[#71849e]">FalkorDB</span>
          </div>

          <div className="flex flex-wrap gap-1.5">
            {(schemaProfile?.node_kinds || [
              "Account",
              "Service",
              "Repository",
              "Task",
              "Person",
              "Policy",
              "AuditRecord",
            ]).slice(0, 8).map((k: any, idx: number) => {
              const kindName = typeof k === "string" ? k : k.kind;
              return (
                <span
                  key={idx}
                  className="px-2 py-0.5 rounded-md bg-[#eff7ff] text-[#1678ef] text-[10px] font-semibold border border-[#1678ef]/15"
                >
                  :{kindName}
                </span>
              );
            })}
          </div>
        </div>

        {/* Recent Investigations */}
        <div className="flex-1 overflow-y-auto px-4 py-3 border-t border-[#4370aa]/15">
          <span className="text-[10px] font-bold uppercase tracking-wider text-[#71849e] mb-2 block">
            Recent Investigations
          </span>
          <div className="space-y-1.5">
            {recentSessions.map((s) => (
              <button
                key={s.id}
                onClick={() => handleRunInvestigation(s.query)}
                className="w-full text-left p-2 rounded-xl text-xs hover:bg-[#eff7ff] border border-transparent hover:border-[#1678ef]/20 transition flex flex-col gap-0.5 group"
              >
                <span className="font-medium text-[#102f58] line-clamp-2 group-hover:text-[#1678ef]">
                  {s.query}
                </span>
                <span className="text-[10px] text-[#71849e]">{s.timestamp}</span>
              </button>
            ))}
          </div>
        </div>
      </aside>

      {/* CENTER PANEL: Investigation Conversation & Agent Stream */}
      <main className="flex-1 flex flex-col min-w-0 border-r border-[#4370aa]/15 bg-white">
        {/* Top Header */}
        <div className="px-6 py-4 border-b border-[#4370aa]/15 flex items-center justify-between bg-white shrink-0">
          <div>
            <h2 className="text-base font-bold text-[#102f58] truncate max-w-xl">
              {currentObjective || "GraphOS Investigation Workspace"}
            </h2>
            <div className="flex items-center gap-2 text-xs text-[#71849e] mt-0.5">
              <span>Universal Agent</span>
              <span>•</span>
              <span className="text-[#1678ef] font-medium">Read-Only Guardrails Enforced</span>
            </div>
          </div>

          {isInvestigating && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#1678ef]/10 text-[#1678ef] text-xs font-semibold border border-[#1678ef]/20">
              <span className="w-2 h-2 rounded-full bg-[#1678ef] animate-ping" />
              <span>Investigating...</span>
            </div>
          )}
        </div>

        {/* Scrollable Conversation / Stream Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {!currentObjective && !currentResult && (
            <div className="flex flex-col items-center justify-center h-full text-center py-12">
              <div className="w-16 h-16 rounded-3xl bg-gradient-to-tr from-[#1678ef]/20 to-[#82c4ff]/20 flex items-center justify-center text-[#1678ef] mb-4">
                <Search className="w-8 h-8" />
              </div>
              <h3 className="text-lg font-bold text-[#102f58]">Begin a Graph Investigation</h3>
              <p className="text-sm text-[#71849e] max-w-md mt-1 mb-6">
                Type an objective below or choose a starter scenario to discover connected entities, trace multi-hop relationship paths, and inspect grounded findings.
              </p>
              <div className="flex flex-wrap gap-2 justify-center max-w-lg">
                {[
                  "Investigate suspicious transactions and find connected entities",
                  "Triage security findings and identify affected databases",
                  "Trace dependencies for Payments Release October 2026",
                ].map((prompt, i) => (
                  <button
                    key={i}
                    onClick={() => handleRunInvestigation(prompt)}
                    className="p-2.5 rounded-xl bg-[#f6faff] hover:bg-[#eff7ff] text-xs font-medium text-[#1678ef] border border-[#1678ef]/20 transition text-left"
                  >
                    "{prompt}"
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* User question bubble */}
          {currentObjective && (
            <div className="flex items-start gap-3 p-4 rounded-2xl bg-[#f6faff] border border-[#4370aa]/15">
              <div className="w-8 h-8 rounded-full bg-[#1678ef] text-white flex items-center justify-center text-xs font-bold shrink-0">
                You
              </div>
              <div className="flex-1">
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#71849e]">
                  Investigation Objective
                </span>
                <p className="text-sm font-semibold text-[#102f58] mt-0.5">
                  {currentObjective}
                </p>
              </div>
            </div>
          )}

          {/* Live Progress Timeline */}
          {events.length > 0 && (
            <div className="p-4 rounded-2xl bg-white border border-[#4370aa]/20 shadow-sm space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-[#4370aa]/10">
                <span className="text-xs font-bold text-[#102f58] flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5 text-[#1678ef]" />
                  <span>Agent Reasoning & Tool Progress</span>
                </span>
                <span className="text-[11px] text-[#71849e]">
                  {events.length} events logged
                </span>
              </div>

              <div className="space-y-2 max-h-56 overflow-y-auto pr-1 text-xs font-mono">
                {events.map((ev, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-2 py-1 px-2 rounded-lg bg-[#f8fbff] border border-[#4370aa]/10"
                  >
                    <span
                      className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase shrink-0 ${
                        ev.type === "tool_call"
                          ? "bg-[#eff7ff] text-[#1678ef]"
                          : ev.type === "tool_result"
                          ? "bg-emerald-50 text-emerald-700"
                          : ev.type === "thought"
                          ? "bg-purple-50 text-purple-700"
                          : ev.type === "error"
                          ? "bg-red-50 text-red-700"
                          : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {ev.type}
                    </span>
                    <span className="text-[#102f58] break-all">{ev.message}</span>
                  </div>
                ))}
              </div>
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
                <div className="flex items-center gap-3 text-xs text-[#71849e]">
                  <span className="inline-flex items-center gap-1">
                    <Zap className="w-3.5 h-3.5 text-[#1678ef]" />
                    <span>{currentResult.duration_seconds}s</span>
                  </span>
                  <span>•</span>
                  <span>{currentResult.total_tool_calls} tool calls</span>
                  <span>•</span>
                  <span>{currentResult.evidence_summary?.unique_entities_count || 0} entities grounded</span>
                </div>
              </div>

              {/* Render Final Answer Markdown text */}
              <div className="prose prose-sm max-w-none text-xs sm:text-sm text-[#102f58] leading-relaxed whitespace-pre-wrap">
                {currentResult.final_answer}
              </div>
            </div>
          )}
        </div>

        {/* Bottom Follow-up Composer */}
        <div className="p-4 border-t border-[#4370aa]/15 bg-[#f6faff]/60 shrink-0">
          <form onSubmit={handleFormSubmit} className="flex items-center gap-2">
            <input
              type="text"
              value={queryInput}
              onChange={(e) => setQueryInput(e.target.value)}
              placeholder="Ask a follow-up or enter a new graph objective..."
              disabled={isInvestigating}
              className="flex-1 px-4 py-2.5 rounded-xl border border-[#4370aa]/20 bg-white text-xs sm:text-sm text-[#102f58] placeholder-[#71849e] focus:outline-none focus:ring-2 focus:ring-[#1678ef]/40 disabled:opacity-50 transition"
            />
            <button
              type="submit"
              disabled={!queryInput.trim() || isInvestigating}
              className="px-4 py-2.5 rounded-xl bg-[#1678ef] hover:bg-[#1b80ff] disabled:opacity-40 text-white font-semibold text-xs flex items-center gap-1.5 transition shrink-0"
            >
              <span>Send</span>
              <Send className="w-3.5 h-3.5" />
            </button>
          </form>
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
        <div className="flex-1 overflow-y-auto p-4">
          {activeTab === "graph" && (
            <div className="space-y-4">
              <GraphExplorer
                entities={currentResult?.evidence_summary?.entities || {}}
                edges={[]}
                keyPaths={currentResult?.evidence_summary?.key_paths || []}
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
              <span className="text-xs font-bold uppercase tracking-wider text-[#71849e] block pb-2 border-b border-[#4370aa]/15">
                Grounded Entities ({currentResult?.evidence_summary?.unique_entities_count || 0})
              </span>

              {(!currentResult?.evidence_summary?.entities ||
                Object.keys(currentResult.evidence_summary.entities).length === 0) && (
                <div className="text-center py-10 text-xs text-[#71849e]">
                  No entities discovered yet.
                </div>
              )}

              {Object.values(currentResult?.evidence_summary?.entities || {}).map((ent) => (
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
                  {ent.is_isolated && (
                    <span className="inline-block px-2 py-0.5 rounded bg-amber-50 text-amber-700 text-[10px] font-semibold">
                      Isolated Node
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}

          {activeTab === "activity" && (
            <div className="space-y-3">
              <span className="text-xs font-bold uppercase tracking-wider text-[#71849e] block pb-2 border-b border-[#4370aa]/15">
                MCP Tool Calls ({currentResult?.steps?.reduce((acc, s) => acc + s.tool_calls.length, 0) || 0})
              </span>

              {currentResult?.steps?.map((step) => (
                <div
                  key={step.iteration}
                  className="p-3 rounded-2xl bg-white border border-[#4370aa]/15 space-y-2 text-xs"
                >
                  <div className="flex items-center justify-between text-[#71849e] text-[11px]">
                    <span className="font-semibold">Step {step.iteration}</span>
                    <span>{step.duration_seconds}s</span>
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
    </div>
  );
}
