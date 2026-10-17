"use client";

import React, { useState } from "react";
import { Sparkles, Activity, Database, Menu, X, ArrowRight } from "lucide-react";
import { HealthStatus } from "../types";

interface NavigationProps {
  health: HealthStatus | null;
  mode: "live" | "demo";
  onToggleMode: () => void;
  onOpenWorkspace: () => void;
}

export function Navigation({
  health,
  mode,
  onToggleMode,
  onOpenWorkspace,
}: NavigationProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <nav className="w-full relative z-30 px-6 lg:px-12 py-5 flex items-center justify-between border-b border-white/[0.08] backdrop-blur-md bg-white/[0.02]">
      {/* Brand logo & wordmark */}
      <div className="flex items-center gap-3">
        <div className="relative flex items-center justify-center w-9 h-9 rounded-xl bg-gradient-to-tr from-[#1678ef] via-[#268cf5] to-[#38bdf8] shadow-[0_0_20px_rgba(38,140,245,0.45)]">
          <Database className="w-5 h-5 text-white" />
          <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-[#38bdf8] animate-ping" />
        </div>
        <div className="flex flex-col text-left">
          <span className="text-xl font-bold tracking-tight text-white flex items-center gap-1.5 drop-shadow-sm">
            Graph<span className="text-transparent bg-clip-text bg-gradient-to-r from-[#60b5ff] to-[#38bdf8]">OS</span>
          </span>
          <span className="text-[10px] uppercase font-semibold tracking-wider text-blue-200/70 -mt-0.5">
            Universal Graph Agent
          </span>
        </div>
      </div>

      {/* Desktop Navigation Links */}
      <div className="hidden md:flex items-center gap-8 text-sm font-medium text-blue-100/80">
        <button onClick={onOpenWorkspace} className="hover:text-white transition">Agent Workspace</button>
        <button onClick={onOpenWorkspace} className="hover:text-white transition">Graph Explorer</button>
        <button onClick={onOpenWorkspace} className="hover:text-white transition">MCP Schema</button>
        <button onClick={onOpenWorkspace} className="hover:text-white transition">Evidence Trails</button>
      </div>

      {/* Right side CTAs & Connection status */}
      <div className="hidden md:flex items-center gap-4">
        {/* Live / Demo Mode Toggle */}
        <button
          onClick={onToggleMode}
          title="Toggle execution mode between live agent and verified demo scenarios"
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-semibold border backdrop-blur-md transition ${
            mode === "live"
              ? "bg-[#1678ef]/25 border-[#38bdf8]/50 text-[#7dd3fc] shadow-[0_0_15px_rgba(22,120,239,0.3)]"
              : "bg-amber-500/20 border-amber-400/40 text-amber-300"
          }`}
        >
          <span className={`w-2 h-2 rounded-full ${mode === "live" ? "bg-[#38bdf8]" : "bg-amber-400"} animate-pulse`} />
          <span>{mode === "live" ? "Live MCP Mode" : "Demo Scenarios"}</span>
        </button>

        {/* Primary CTA: Launch Workspace */}
        <button
          onClick={onOpenWorkspace}
          className="flex items-center gap-2 px-4.5 py-2 rounded-full text-xs font-semibold text-white bg-gradient-to-r from-[#1678ef] via-[#268cf5] to-[#00d2ff] hover:brightness-110 shadow-[0_0_20px_rgba(22,120,239,0.5)] hover:shadow-[0_0_30px_rgba(0,210,255,0.7)] transition transform hover:-translate-y-0.5 active:translate-y-0"
        >
          <span>Launch Workspace</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Mobile menu trigger */}
      <div className="md:hidden flex items-center gap-2">
        <button
          onClick={onOpenWorkspace}
          className="px-3 py-1.5 rounded-full text-xs font-semibold text-white bg-[#1678ef]"
        >
          Workspace
        </button>
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="p-2 text-white/80 hover:text-white"
        >
          {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Mobile dropdown */}
      {mobileMenuOpen && (
        <div className="absolute top-full left-0 w-full bg-[#061a38]/95 backdrop-blur-xl border-b border-white/10 p-6 flex flex-col gap-4 text-white text-sm md:hidden animate-in slide-in-from-top-2">
          <button onClick={() => { setMobileMenuOpen(false); onOpenWorkspace(); }} className="text-left py-1 hover:text-[#38bdf8]">Agent Workspace</button>
          <button onClick={() => { setMobileMenuOpen(false); onOpenWorkspace(); }} className="text-left py-1 hover:text-[#38bdf8]">Graph Explorer</button>
          <button onClick={() => { setMobileMenuOpen(false); onOpenWorkspace(); }} className="text-left py-1 hover:text-[#38bdf8]">MCP Schema</button>
          <button onClick={() => { setMobileMenuOpen(false); onOpenWorkspace(); }} className="text-left py-1 hover:text-[#38bdf8]">Evidence Trails</button>
          <div className="pt-2 border-t border-white/10 flex items-center justify-between">
            <span className="text-xs text-white/60">Execution Engine</span>
            <button
              onClick={onToggleMode}
              className="text-xs px-3 py-1 rounded-full border border-white/20"
            >
              Mode: {mode.toUpperCase()}
            </button>
          </div>
        </div>
      )}
    </nav>
  );
}
