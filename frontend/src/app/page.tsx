"use client";

import React, { useState, useEffect } from "react";
import { Hero } from "../components/Hero";
import { Workspace } from "../components/Workspace";
import { ImportDatasetModal } from "../components/ImportDatasetModal";
import { HealthStatus, GraphSchemaProfile } from "../types";
import { getHealth, getSchema, getAvailableGraphs } from "../lib/api";
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
  const [availableGraphs, setAvailableGraphs] = useState<string[]>(["ALL_GRAPHS"]);

  useEffect(() => {
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
    setView("workspace");
  };

  const handleOpenWorkspace = () => {
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
    setView("workspace");
  };

  if (view === "workspace") {
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
        <header className="relative z-30 max-w-7xl mx-auto px-6 py-2 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-[#1678ef] to-[#38bdf8] flex items-center justify-center text-white shadow-md shadow-blue-500/20">
              <Network className="w-5 h-5" />
            </div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-lg tracking-tight text-white">
                GraphOS
              </span>
              <span className="text-[10px] font-bold font-mono tracking-wider text-[#38bdf8] bg-white/10 px-2 py-0.5 rounded-full border border-[#38bdf8]/30">
                v1.0
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsImportModalOpen(true)}
              className="hidden sm:flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-white/10 hover:bg-white/20 border border-white/20 text-white backdrop-blur-md transition shadow-xs cursor-pointer"
              title="Import AST JSON, Live CSV, or Dataset"
            >
              <Upload className="w-3.5 h-3.5 text-[#38bdf8]" />
              <span>Import Dataset</span>
            </button>

            <div
              className="flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-semibold border border-[#38bdf8]/40 bg-[#1678ef]/20 text-[#7dd3fc] backdrop-blur-md shadow-xs"
              title="Live FalkorDB MCP Knowledge Graph Agent"
            >
              <span className="w-2 h-2 rounded-full bg-[#38bdf8] animate-pulse" />
              <span className="hidden md:inline">Live MCP · FalkorDB Active</span>
              <span className="md:hidden">Live MCP</span>
            </div>

            <button
              onClick={handleOpenWorkspace}
              className="flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-bold text-white bg-gradient-to-r from-[#1678ef] to-[#0ea5e9] hover:brightness-110 shadow-md shadow-blue-500/30 transition transform hover:-translate-y-0.5 active:translate-y-0 cursor-pointer"
            >
              <span>Launch Chatbot</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </header>

        {/* Clean, attractive product hero without raw chatbox */}
        <Hero
          onStartInvestigation={handleStartInvestigation}
          onOpenWorkspace={handleOpenWorkspace}
          onOpenImport={() => setIsImportModalOpen(true)}
          mode="live"
        />

        {/* Luminous Arch Curve */}
        <div className="absolute -bottom-px left-0 right-0 w-full overflow-hidden leading-none pointer-events-none z-10">
          <svg
            viewBox="0 0 1440 140"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="w-full h-14 sm:h-20 md:h-28 block"
            preserveAspectRatio="none"
          >
            <defs>
              <linearGradient id="horizonArchGlow" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#1678ef" stopOpacity="0.2" />
                <stop offset="25%" stopColor="#38bdf8" stopOpacity="0.85" />
                <stop offset="50%" stopColor="#ffffff" stopOpacity="1" />
                <stop offset="75%" stopColor="#38bdf8" stopOpacity="0.85" />
                <stop offset="100%" stopColor="#1678ef" stopOpacity="0.2" />
              </linearGradient>
              <filter id="archNeonBlur" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="5" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Glowing neon horizon atmospheric rim curve */}
            <path
              d="M 0,80 Q 720,0 1440,80"
              stroke="url(#horizonArchGlow)"
              strokeWidth="4"
              fill="none"
              filter="url(#archNeonBlur)"
            />

            {/* Crisp inner arch line */}
            <path
              d="M 0,80 Q 720,0 1440,80"
              stroke="#ffffff"
              strokeWidth="1.5"
              fill="none"
              opacity="0.9"
            />

            {/* Fill beneath the arch with the clean section color */}
            <path
              d="M 0,80 Q 720,0 1440,80 L 1440,140 L 0,140 Z"
              fill="#f6faff"
            />
          </svg>
        </div>
      </div>

      {/* "How It Works" Section — Clean, Modern, Informative */}
      <section className="relative w-full max-w-6xl mx-auto px-6 pt-8 pb-16">
        <div className="text-center max-w-2xl mx-auto mb-12">
          <span className="text-xs font-bold uppercase tracking-wider text-[#1678ef] bg-[#eff7ff] px-3 py-1 rounded-full border border-[#1678ef]/20">
            How It Works
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-[#102f58] tracking-tight mt-3">
            Autonomous Graph Intelligence in 3 Steps
          </h2>
          <p className="text-sm sm:text-base text-[#71849e] mt-2 leading-relaxed">
            From natural language objectives to verified, multi-hop relationship findings backed by FalkorDB.
          </p>
        </div>

        {/* 3 Step Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Step 1 */}
          <div className="p-6 rounded-3xl bg-white border border-[#4370aa]/15 shadow-sm hover:shadow-md hover:border-[#1678ef]/40 transition flex flex-col justify-between gap-4">
            <div>
              <div className="w-12 h-12 rounded-2xl bg-[#eff7ff] text-[#1678ef] flex items-center justify-center mb-4">
                <Database className="w-6 h-6" />
              </div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#1678ef]">
                Step 01
              </span>
              <h3 className="text-lg font-bold text-[#102f58] mt-1">
                Dynamic Schema Discovery
              </h3>
              <p className="text-xs text-[#71849e] leading-relaxed mt-2">
                Connects directly to FalkorDB via MCP or imports code ASTs and CSVs. Discovers entity types, attributes, and connection topologies on the fly with zero hardcoding.
              </p>
            </div>
            <div className="pt-3 border-t border-slate-100 flex items-center gap-2 text-[11px] font-semibold text-emerald-600">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Zero-Config Dynamic Ingestion</span>
            </div>
          </div>

          {/* Step 2 */}
          <div className="p-6 rounded-3xl bg-white border border-[#4370aa]/15 shadow-sm hover:shadow-md hover:border-[#1678ef]/40 transition flex flex-col justify-between gap-4">
            <div>
              <div className="w-12 h-12 rounded-2xl bg-[#eff7ff] text-[#1678ef] flex items-center justify-center mb-4">
                <Cpu className="w-6 h-6" />
              </div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#1678ef]">
                Step 02
              </span>
              <h3 className="text-lg font-bold text-[#102f58] mt-1">
                Autonomous Multi-Hop Reasoning
              </h3>
              <p className="text-xs text-[#71849e] leading-relaxed mt-2">
                The agent parses objectives, formulates guarded read-only Cypher queries, and executes iterative tool calls to trace complex multi-hop paths across disparate graphs.
              </p>
            </div>
            <div className="pt-3 border-t border-slate-100 flex items-center gap-2 text-[11px] font-semibold text-blue-600">
              <Lock className="w-3.5 h-3.5" />
              <span>Read-Only Cypher Guardrails</span>
            </div>
          </div>

          {/* Step 3 */}
          <div className="p-6 rounded-3xl bg-white border border-[#4370aa]/15 shadow-sm hover:shadow-md hover:border-[#1678ef]/40 transition flex flex-col justify-between gap-4">
            <div>
              <div className="w-12 h-12 rounded-2xl bg-[#eff7ff] text-[#1678ef] flex items-center justify-center mb-4">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#1678ef]">
                Step 03
              </span>
              <h3 className="text-lg font-bold text-[#102f58] mt-1">
                Grounded Evidence & Topology
              </h3>
              <p className="text-xs text-[#71849e] leading-relaxed mt-2">
                Visualizes the exact subgraphs in an interactive topology canvas. Every claim cites exact node IDs, evidence paths, and confidence scores with zero hallucination.
              </p>
            </div>
            <div className="pt-3 border-t border-slate-100 flex items-center gap-2 text-[11px] font-semibold text-indigo-600">
              <GitBranch className="w-3.5 h-3.5" />
              <span>100% Provenance & Human Approval</span>
            </div>
          </div>
        </div>

        {/* Live Knowledge Graph Status Banner with Highlighted Button */}
        <div className="mt-12 p-6 sm:p-7 rounded-3xl bg-white border border-[#4370aa]/20 shadow-xl flex flex-col md:flex-row items-center justify-between gap-6 hover:border-[#1678ef]/40 transition">
          <div className="flex flex-col gap-1 text-center md:text-left">
            <div className="flex items-center justify-center md:justify-start gap-2 text-xs font-semibold uppercase tracking-wider text-[#1678ef]">
              <Database className="w-4 h-4" />
              <span>Connected Knowledge Graph</span>
            </div>
            <p className="text-sm font-semibold text-[#102f58]">
              Live FalkorDB MCP Server Active — Dynamic Schema Traversal Ready
            </p>
            {schemaProfile && schemaProfile.node_kinds.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 mt-2 justify-center md:justify-start">
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
                      className="px-2.5 py-0.5 rounded-md bg-[#eff7ff] hover:bg-[#1678ef] text-[#1678ef] hover:text-white text-xs font-mono font-medium border border-[#1678ef]/15 transition cursor-pointer"
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
              className="flex items-center gap-2 px-4 py-3 rounded-2xl text-xs font-semibold text-[#1678ef] bg-[#eff7ff] hover:bg-[#1678ef]/10 border border-[#1678ef]/20 transition cursor-pointer"
            >
              <Upload className="w-4 h-4" />
              <span>Import Dataset</span>
            </button>
            <button
              onClick={handleOpenWorkspace}
              className="flex items-center gap-2 px-6 py-3 rounded-2xl text-xs font-bold text-white bg-gradient-to-r from-[#1678ef] via-[#2563eb] to-[#0ea5e9] hover:brightness-110 shadow-lg shadow-blue-500/30 transition transform hover:-translate-y-0.5 active:translate-y-0 cursor-pointer"
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
