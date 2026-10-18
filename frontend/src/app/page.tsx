"use client";

import React, { useState, useEffect } from "react";
import { Hero } from "../components/Hero";
import { Workspace } from "../components/Workspace";
import { InteractiveDotGrid } from "../components/InteractiveDotGrid";
import { ImportDatasetModal } from "../components/ImportDatasetModal";
import { HealthStatus, GraphSchemaProfile } from "../types";
import { getHealth, getSchema, getAvailableGraphs } from "../lib/api";
import { Database, Network, ArrowRight, ShieldCheck, Activity, Sparkles, Upload } from "lucide-react";

export default function Home() {
  const [view, setView] = useState<"landing" | "workspace">("landing");
  const [mode, setMode] = useState<"live" | "demo">("live");
  const [activeQuery, setActiveQuery] = useState<string>("");
  const [selectedGraph, setSelectedGraph] = useState<string>("ALL_GRAPHS");
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [schemaProfile, setSchemaProfile] = useState<GraphSchemaProfile | null>(null);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [availableGraphs, setAvailableGraphs] = useState<string[]>([
    "ALL_GRAPHS",
    "fraud_swiftpay",
    "graphos_dev",
    "security_swiftpay",
    "fraud_Front",
    "swiftpay_unified",
  ]);

  useEffect(() => {
    getHealth().then((h) => {
      setHealth(h);
      if (!h) {
        setMode("demo");
      }
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
    setView("workspace");
  };

  const handleBackToLanding = () => {
    setView("landing");
  };

  const handleToggleMode = () => {
    setMode((prev) => (prev === "live" ? "demo" : "live"));
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
        initialMode={mode}
        initialGraph={selectedGraph}
        onBackToLanding={handleBackToLanding}
      />
    );
  }

  return (
    <main className="min-h-screen bg-[#f6faff] flex flex-col justify-between overflow-x-hidden">
      {/* Top Hero with rich luminous gradient, starfield, nebula glow, and celestial arch */}
      <div className="relative hero-gradient-container w-full text-white pt-6 pb-20 md:pb-28">
        {/* Starfield overlay layer */}
        <div className="star-texture-layer" />

        {/* Ambient celestial glow orb behind the headline */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[950px] h-[450px] ambient-glow pointer-events-none rounded-full blur-3xl opacity-80" />

        {/* Clean top corner mode toggle & dataset import */}
        <div className="relative z-30 max-w-7xl mx-auto px-6 flex items-center justify-end gap-3">
          <button
            onClick={() => setIsImportModalOpen(true)}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-white/10 hover:bg-white/20 border border-white/25 text-white backdrop-blur-md transition shadow-sm cursor-pointer"
            title="Import CLI Code Parser JSON, Live CSV, or Connect Supabase"
          >
            <Upload className="w-3.5 h-3.5 text-[#38bdf8]" />
            <span>Import Dataset</span>
          </button>

          <button
            onClick={handleToggleMode}
            title="Toggle execution mode between live agent and verified demo scenarios"
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-semibold border backdrop-blur-md transition shadow-sm cursor-pointer ${
              mode === "live"
                ? "bg-[#1678ef]/30 border-[#38bdf8]/50 text-[#7dd3fc] hover:bg-[#1678ef]/40"
                : "bg-amber-500/20 border-amber-400/40 text-amber-300 hover:bg-amber-500/30"
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                mode === "live" ? "bg-[#38bdf8]" : "bg-amber-400"
              } animate-pulse`}
            />
            <span>{mode === "live" ? "Live MCP Mode" : "Demo Scenarios"}</span>
          </button>
        </div>

        {/* Main Hero with interactive prompt composer */}
        <Hero
          onStartInvestigation={handleStartInvestigation}
          mode={mode}
        />

        {/* Luminous Arch Curve as shown in reference image */}
        <div className="absolute -bottom-px left-0 right-0 w-full overflow-hidden leading-none pointer-events-none z-10">
          <svg
            viewBox="0 0 1440 140"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="w-full h-16 sm:h-24 md:h-32 block"
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

            {/* Fill beneath the arch with the white/ice section color */}
            <path
              d="M 0,80 Q 720,0 1440,80 L 1440,140 L 0,140 Z"
              fill="#f6faff"
            />
          </svg>
        </div>
      </div>

      {/* White/Ice Section with Glowing Interactive Dot Grid */}
      <div className="relative flex-1 bg-[#f6faff] min-h-[320px] flex flex-col items-center justify-center px-4 sm:px-6 py-12 overflow-hidden">
        {/* Interactive Glowing Dot Grid Canvas reacting to cursor proximity */}
        <InteractiveDotGrid />

        {/* Live Knowledge Graph Status Card — 100% interactive, zero dummy data */}
        <div className="relative z-10 w-full max-w-4xl p-6 sm:p-7 rounded-3xl bg-white/95 backdrop-blur-md border border-[#4370aa]/20 shadow-xl flex flex-col md:flex-row items-center justify-between gap-6 hover:border-[#1678ef]/40 transition">
          <div className="flex flex-col gap-1 text-center md:text-left">
            <div className="flex items-center justify-center md:justify-start gap-2 text-xs font-semibold uppercase tracking-wider text-[#1678ef]">
              <Database className="w-4 h-4" />
              <span>Connected Knowledge Graph</span>
            </div>
            <p className="text-sm font-semibold text-[#102f58]">
              {mode === "live"
                ? "Live FalkorDB MCP Server Active — Dynamic Schema Traversal Ready"
                : "Verified Offline Demonstrations Mode Active"}
            </p>
            {schemaProfile && schemaProfile.node_kinds.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 mt-2 justify-center md:justify-start">
                <span className="text-xs text-[#71849e] font-medium mr-1">Discovered Types:</span>
                {schemaProfile.node_kinds.slice(0, 7).map((k: any, i: number) => {
                  const label = typeof k === "string" ? k : k.kind;
                  return (
                    <button
                      key={i}
                      onClick={() => handleStartInvestigation(`Investigate connected entities of kind :${label}`)}
                      className="px-2.5 py-0.5 rounded-md bg-[#eff7ff] hover:bg-[#1678ef] text-[#1678ef] hover:text-white text-xs font-mono font-medium border border-[#1678ef]/15 transition"
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
              className="flex items-center gap-2 px-6 py-3 rounded-2xl text-xs font-semibold text-white bg-gradient-to-r from-[#1678ef] via-[#268cf5] to-[#00d2ff] hover:brightness-110 shadow-lg shadow-[#1678ef]/30 transition transform hover:-translate-y-0.5 active:translate-y-0 cursor-pointer"
            >
              <span>Open Chatbot Workspace</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

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
