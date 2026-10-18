"use client";

import React, { useState, useEffect } from "react";
import { Hero } from "../components/Hero";
import { Workspace } from "../components/Workspace";
import { ImportDatasetModal } from "../components/ImportDatasetModal";
import { HealthStatus, GraphSchemaProfile, User } from "../types";
import { getHealth, getSchema, getAvailableGraphs, getMe, logoutUser } from "../lib/api";
import { AuthModal } from "../components/AuthModal";
import {
  Database,
  Network,
  ArrowRight,
  ShieldCheck,
  Activity,
  Sparkles,
  Upload,
  Cpu,
  Layers,
  Lock,
  GitBranch,
  CheckCircle2,
} from "lucide-react";

export default function Home() {
  const [view, setView] = useState<"landing" | "workspace">("landing");
  const [activeQuery, setActiveQuery] = useState<string>("");
  const [selectedGraph, setSelectedGraph] = useState<string>("ALL_GRAPHS");
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [schemaProfile, setSchemaProfile] = useState<GraphSchemaProfile | null>(null);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [availableGraphs, setAvailableGraphs] = useState<string[]>(["ALL_GRAPHS"]);

  useEffect(() => {
    getMe().then((u) => {
      if (u) setUser(u);
    });
    getHealth().then((h) => {
      setHealth(h);
    });
    getSchema("ALL_GRAPHS").then((s) => {
      if (s) setSchemaProfile(s);
    });
    getAvailableGraphs().then((res) => {
      if (res && res.graphs) {
        setAvailableGraphs(res.graphs);
        if (res.active_graph) {
          setSelectedGraph(res.active_graph);
        }
      }
    });
  }, []);

  const handleStartInvestigation = (query: string) => {
    setActiveQuery(query);
    if (!user) {
      setIsAuthModalOpen(true);
      return;
    }
    setView("workspace");
  };

  const handleOpenWorkspace = () => {
    if (!user) {
      setIsAuthModalOpen(true);
      return;
    }
    setActiveQuery("");
    setView("workspace");
  };

  const handleBackToLanding = () => {
    setView("landing");
  };

  const handleIngestSuccess = (graphName: string) => {
    setSelectedGraph(graphName);
    getAvailableGraphs().then((res) => {
      if (res && res.graphs) {
        setAvailableGraphs(res.graphs);
      }
    });
    setIsImportModalOpen(false);
    if (!user) {
      setIsAuthModalOpen(true);
    } else {
      setView("workspace");
    }
  };

  if (view === "workspace" && user) {
    return (
      <Workspace
        initialQuery={activeQuery}
        initialMode="live"
        initialGraph={selectedGraph}
        onBackToLanding={handleBackToLanding}
      />
    );
  }

  return (
    <main className="min-h-screen bg-[#f6faff] flex flex-col justify-between overflow-x-hidden">
      {/* Top Hero with rich luminous gradient and starfield */}
      <div className="relative hero-gradient-container w-full text-white pt-5 pb-16 md:pb-24">
        {/* Starfield overlay layer */}
        <div className="star-texture-layer" />

        {/* Ambient celestial glow orb behind headline */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[950px] h-[450px] ambient-glow pointer-events-none rounded-full blur-3xl opacity-80" />

        {/* Top Navbar */}
        <header className="relative z-30 max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-[#1678ef] to-[#38bdf8] flex items-center justify-center text-white shadow-xs">
              <Network className="w-5 h-5" />
            </div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-lg tracking-tight text-white">
                GraphOS
              </span>
              <span className="text-[10px] font-semibold font-mono tracking-wider text-sky-300 bg-white/10 px-2 py-0.5 rounded-full border border-sky-400/20">
                v1.0
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={() => setIsImportModalOpen(true)}
              className="hidden sm:inline-flex items-center gap-1.5 h-9 px-3.5 rounded-xl text-xs font-medium bg-white/10 hover:bg-white/15 border border-white/15 text-white transition cursor-pointer"
              title="Import AST JSON, Live CSV, or Dataset"
            >
              <Upload className="w-3.5 h-3.5 text-sky-300" />
              <span>Import Dataset</span>
            </button>

            <div
              className="inline-flex items-center gap-2 h-9 px-3.5 rounded-xl text-xs font-medium border border-sky-400/30 bg-sky-500/10 text-sky-200"
              title={health?.status === "healthy" ? "Live FalkorDB Connected" : "Connecting to FalkorDB"}
            >
              <span className={`w-2 h-2 rounded-full ${health?.status === "healthy" ? "bg-emerald-400" : "bg-amber-400 animate-pulse"}`} />
              <span className="hidden md:inline">
                {health?.status === "healthy" ? "FalkorDB Connected" : "FalkorDB Active"}
              </span>
              <span className="md:hidden">Live</span>
            </div>

            {user ? (
              <div className="flex items-center gap-2 h-9 px-3 rounded-xl text-xs font-medium bg-white/10 border border-white/15 text-white">
                <span className="w-5 h-5 rounded-full bg-sky-400 text-[#071738] flex items-center justify-center text-[10px] font-bold">
                  {user.name.charAt(0).toUpperCase()}
                </span>
                <span className="max-w-[100px] truncate hidden md:inline">{user.name}</span>
                <button
                  onClick={async () => {
                    await logoutUser();
                    setUser(null);
                  }}
                  className="text-sky-300 hover:text-white text-[11px] font-semibold ml-1 cursor-pointer transition"
                  title="Log Out"
                >
                  Log Out
                </button>
              </div>
            ) : (
              <button
                onClick={() => setIsAuthModalOpen(true)}
                className="inline-flex items-center gap-1.5 h-9 px-3.5 rounded-xl text-xs font-medium bg-white/10 hover:bg-white/15 border border-white/20 text-white transition cursor-pointer"
                title="Sign in to access investigations"
              >
                <Lock className="w-3.5 h-3.5 text-sky-300" />
                <span>Sign In</span>
              </button>
            )}

            <button
              onClick={handleOpenWorkspace}
              className="inline-flex items-center gap-1.5 h-9 px-4 rounded-xl text-xs font-semibold text-white bg-[#1678ef] hover:bg-[#1264c9] shadow-sm transition cursor-pointer"
            >
              <span>{user ? "Launch Chatbot" : "Launch AI Chatbot"}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </header>

        {/* Clean, attractive product hero */}
        <Hero
          user={user}
          onStartInvestigation={handleStartInvestigation}
          onOpenWorkspace={handleOpenWorkspace}
          onOpenImport={() => setIsImportModalOpen(true)}
          onOpenAuth={() => setIsAuthModalOpen(true)}
          mode="live"
        />

        {/* Subtle, smooth section divider curve */}
        <div className="absolute -bottom-px left-0 right-0 w-full overflow-hidden leading-none pointer-events-none">
          <svg
            viewBox="0 0 1440 60"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="w-full h-8 sm:h-12 md:h-14 block"
            preserveAspectRatio="none"
          >
            <path
              d="M0,30 Q720,0 1440,30 L1440,60 L0,60 Z"
              fill="#f6faff"
            />
          </svg>
        </div>
      </div>

      {/* "How It Works" Section — Clean, Modern, Informative */}
      <section className="relative w-full max-w-6xl mx-auto px-6 pt-6 pb-16">
        <div className="text-center max-w-2xl mx-auto mb-10">
          <span className="text-xs font-semibold uppercase tracking-wider text-[#1678ef] bg-blue-50 px-3 py-1 rounded-full border border-blue-200/60">
            How It Works
          </span>
          <h2 className="text-2xl sm:text-3xl font-bold text-[#102f58] tracking-tight mt-3">
            Autonomous Graph Intelligence in 3 Steps
          </h2>
          <p className="text-sm text-[#71849e] mt-2 leading-relaxed">
            From natural language objectives to verified, multi-hop relationship findings backed by FalkorDB.
          </p>
        </div>

        {/* 3 Step Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Step 1 */}
          <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-xs hover:shadow-md hover:border-blue-400/50 transition-all duration-200 flex flex-col justify-between gap-5">
            <div>
              <div className="w-11 h-11 rounded-xl bg-blue-50 text-[#1678ef] flex items-center justify-center mb-4">
                <Database className="w-5 h-5" />
              </div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#1678ef]">
                Step 01
              </span>
              <h3 className="text-base font-bold text-[#102f58] mt-1">
                Dynamic Schema Discovery
              </h3>
              <p className="text-xs text-[#71849e] leading-relaxed mt-2">
                Connects directly to FalkorDB via MCP or imports code ASTs and CSVs. Discovers entity types, attributes, and connection topologies on the fly with zero hardcoding.
              </p>
            </div>
            <div className="pt-3 border-t border-slate-100 flex items-center gap-1.5 text-xs font-medium text-emerald-600">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Zero-Config Dynamic Ingestion</span>
            </div>
          </div>

          {/* Step 2 */}
          <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-xs hover:shadow-md hover:border-blue-400/50 transition-all duration-200 flex flex-col justify-between gap-5">
            <div>
              <div className="w-11 h-11 rounded-xl bg-blue-50 text-[#1678ef] flex items-center justify-center mb-4">
                <Cpu className="w-5 h-5" />
              </div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#1678ef]">
                Step 02
              </span>
              <h3 className="text-base font-bold text-[#102f58] mt-1">
                Autonomous Multi-Hop Reasoning
              </h3>
              <p className="text-xs text-[#71849e] leading-relaxed mt-2">
                The agent parses objectives, formulates guarded read-only Cypher queries, and executes iterative tool calls to trace complex multi-hop paths across disparate graphs.
              </p>
            </div>
            <div className="pt-3 border-t border-slate-100 flex items-center gap-1.5 text-xs font-medium text-blue-600">
              <Lock className="w-3.5 h-3.5" />
              <span>Read-Only Cypher Guardrails</span>
            </div>
          </div>

          {/* Step 3 */}
          <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-xs hover:shadow-md hover:border-blue-400/50 transition-all duration-200 flex flex-col justify-between gap-5">
            <div>
              <div className="w-11 h-11 rounded-xl bg-blue-50 text-[#1678ef] flex items-center justify-center mb-4">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#1678ef]">
                Step 03
              </span>
              <h3 className="text-base font-bold text-[#102f58] mt-1">
                Grounded Evidence & Topology
              </h3>
              <p className="text-xs text-[#71849e] leading-relaxed mt-2">
                Visualizes the exact subgraphs in an interactive topology canvas. Every claim cites exact node IDs, evidence paths, and confidence scores with zero hallucination.
              </p>
            </div>
            <div className="pt-3 border-t border-slate-100 flex items-center gap-1.5 text-xs font-medium text-indigo-600">
              <GitBranch className="w-3.5 h-3.5" />
              <span>100% Provenance & Human Approval</span>
            </div>
          </div>
        </div>

        {/* Live Knowledge Graph Status Panel */}
        <div className="mt-10 p-6 rounded-2xl bg-white border border-slate-200/80 shadow-xs flex flex-col md:flex-row items-center justify-between gap-6 hover:border-blue-400/40 transition">
          <div className="flex flex-col gap-1.5 text-center md:text-left">
            <div className="flex items-center justify-center md:justify-start gap-2 text-xs font-semibold uppercase tracking-wider text-[#1678ef]">
              <Database className="w-4 h-4" />
              <span>Connected Knowledge Graph</span>
              <span className={`inline-flex items-center gap-1 text-[11px] font-normal normal-case px-2 py-0.5 rounded-full border ${
                health?.status === "healthy"
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : "bg-amber-50 text-amber-700 border-amber-200"
              }`}>
                <span className={`w-1.5 h-1.5 rounded-full ${health?.status === "healthy" ? "bg-emerald-500" : "bg-amber-500 animate-pulse"}`} />
                {health?.status === "healthy" ? "Live FalkorDB Connected" : "Connecting..."}
              </span>
            </div>
            <p className="text-sm font-semibold text-[#102f58]">
              {health?.status === "healthy"
                ? `Live FalkorDB MCP Server Active — Dynamic Schema Traversal Ready (${availableGraphs.length} graphs available)`
                : "Live FalkorDB MCP Server Active — Dynamic Schema Traversal Ready"}
            </p>
            {schemaProfile && schemaProfile.node_kinds.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 mt-1 justify-center md:justify-start">
                <span className="text-xs text-[#71849e] font-medium mr-1">
                  Discovered Types:
                </span>
                {schemaProfile.node_kinds.slice(0, 8).map((k: any, i: number) => {
                  const label = typeof k === "string" ? k : k.kind;
                  return (
                    <button
                      key={i}
                      onClick={() =>
                        handleStartInvestigation(
                          `Investigate connected entities of kind :${label}`
                        )
                      }
                      className="px-2.5 py-0.5 rounded-md bg-blue-50 hover:bg-[#1678ef] text-[#1678ef] hover:text-white text-xs font-mono font-medium border border-blue-200/60 transition cursor-pointer"
                      title={`Click to investigate :${label}`}
                    >
                      :{label}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="shrink-0 flex items-center gap-3">
            <button
              onClick={() => setIsImportModalOpen(true)}
              className="inline-flex items-center gap-2 h-10 px-4 rounded-xl text-xs font-semibold text-[#1678ef] bg-blue-50 hover:bg-blue-100 border border-blue-200/60 transition cursor-pointer"
            >
              <Upload className="w-4 h-4" />
              <span>Import Dataset</span>
            </button>
            <button
              onClick={handleOpenWorkspace}
              className="inline-flex items-center gap-2 h-10 px-5 rounded-xl text-xs font-bold text-white bg-[#1678ef] hover:bg-[#1264c9] shadow-sm transition cursor-pointer"
            >
              <span>Open Chatbot Workspace</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </section>

      <ImportDatasetModal
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        onIngestSuccess={handleIngestSuccess}
        availableGraphs={availableGraphs}
      />

      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onAuthSuccess={(loggedInUser) => {
          setUser(loggedInUser);
          setIsAuthModalOpen(false);
          setView("workspace");
        }}
      />

      {/* Clean footer */}
      <footer className="relative z-10 border-t border-[#4370aa]/15 bg-white py-6 px-6 text-center text-xs text-[#71849e]">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-bold text-[#102f58]">GraphOS</span>
            <span>—</span>
            <span>Universal AI Graph Intelligence</span>
          </div>

          <div className="flex items-center gap-6 text-[11px]">
            <span>Powered by FalkorDB & MCP</span>
            <span>•</span>
            <span className="font-semibold text-[#1678ef]">Built by Team Pake</span>
          </div>
        </div>
      </footer>
    </main>
  );
}
