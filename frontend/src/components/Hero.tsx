"use client";

import React from "react";
import { Sparkles, ArrowRight, Upload } from "lucide-react";

interface HeroProps {
  onStartInvestigation?: (query: string) => void;
  onOpenWorkspace: () => void;
  onOpenImport: () => void;
  mode?: "live" | "demo";
}

export function Hero({
  onOpenWorkspace,
  onOpenImport,
}: HeroProps) {
  return (
    <div className="relative pt-6 pb-16 md:pt-10 md:pb-24 px-4 sm:px-6 lg:px-8 flex flex-col items-center text-center z-20">
      {/* Top pill badge */}
      <div className="inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-white/10 border border-white/20 text-white text-xs font-medium backdrop-blur-md mb-8 shadow-sm">
        <span className="px-2 py-0.5 rounded-full bg-emerald-400 text-[#061a38] text-[10px] font-extrabold uppercase tracking-wider">
          LIVE MCP
        </span>
        <span className="text-white/90">
          Autonomous FalkorDB Knowledge Graph Intelligence
        </span>
      </div>

      {/* Primary Headline with gradient glow */}
      <h1 className="max-w-4xl text-5xl sm:text-6xl md:text-7xl font-extrabold tracking-tight text-white leading-[1.08] drop-shadow-[0_4px_30px_rgba(0,0,0,0.4)]">
        Graph intelligence,
        <br />
        <span className="italic font-serif text-transparent bg-clip-text bg-gradient-to-r from-[#60b5ff] via-[#82c4ff] to-[#38bdf8] font-normal drop-shadow-[0_0_35px_rgba(56,189,248,0.5)]">
          powered by AI
        </span>
      </h1>

      {/* Concise, impactful description */}
      <p className="mt-5 max-w-2xl text-base sm:text-lg text-blue-100/90 leading-relaxed font-normal">
        One engine for dynamic graph discovery, autonomous multi-hop Cypher reasoning,
        and 100% verified evidence provenance. Ask questions in natural language — explore
        insights visually.
      </p>

      {/* Prominent Call to Action Buttons */}
      <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4 w-full max-w-md">
        {/* Highlighted Primary Button */}
        <button
          onClick={onOpenWorkspace}
          className="w-full sm:w-auto flex items-center justify-center gap-3 px-8 py-4 rounded-2xl text-base font-bold text-white bg-gradient-to-r from-[#1678ef] via-[#2563eb] to-[#0ea5e9] hover:brightness-110 shadow-2xl shadow-blue-500/40 hover:shadow-blue-500/60 transition transform hover:-translate-y-0.5 active:translate-y-0 cursor-pointer border border-white/20"
        >
          <Sparkles className="w-5 h-5 text-sky-200" />
          <span>Launch AI Chatbot</span>
          <ArrowRight className="w-5 h-5" />
        </button>

        {/* Secondary Import Button */}
        <button
          onClick={onOpenImport}
          className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-4 rounded-2xl text-sm font-semibold text-white/90 hover:text-white bg-white/10 hover:bg-white/20 border border-white/20 backdrop-blur-md transition cursor-pointer"
        >
          <Upload className="w-4 h-4 text-[#38bdf8]" />
          <span>Import Dataset</span>
        </button>
      </div>
    </div>
  );
}

