"use client";

import React from "react";
import { Sparkles, ArrowRight, Upload, ShieldCheck, UserCheck } from "lucide-react";
import { User } from "../types";

interface HeroProps {
  onStartInvestigation?: (query: string) => void;
  onOpenWorkspace: () => void;
  onOpenImport: () => void;
  mode?: "live" | "demo";
  user?: User | null;
  onOpenAuth?: () => void;
}

export function Hero({
  onOpenWorkspace,
  onOpenImport,
  user,
  onOpenAuth,
}: HeroProps) {
  const handlePrimaryClick = () => {
    if (!user && onOpenAuth) {
      onOpenAuth();
    } else {
      onOpenWorkspace();
    }
  };

  return (
    <div className="relative pt-6 pb-12 md:pt-10 md:pb-16 px-4 sm:px-6 lg:px-8 flex flex-col items-center text-center z-20">
      {/* Top pill badge */}
      {user ? (
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white/10 border border-white/20 text-white text-xs font-medium backdrop-blur-md mb-6 shadow-xs">
          <span className="px-2 py-0.5 rounded-full bg-emerald-400 text-[#071738] text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">
            <UserCheck className="w-3 h-3" /> Logged In
          </span>
          <span className="text-white/90">
            Welcome back, <strong className="text-sky-300">{user.name}</strong> · Chatbot Ready
          </span>
        </div>
      ) : (
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white/10 border border-white/20 text-white text-xs font-medium backdrop-blur-md mb-6 shadow-xs">
          <span className="w-2 h-2 rounded-full bg-sky-400" />
          <span className="text-blue-100">
            Universal AI Graph Intelligence Platform
          </span>
        </div>
      )}

      {/* Primary Headline */}
      <h1 className="max-w-4xl text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight text-white leading-[1.12]">
        Graph intelligence,{" "}
        <span className="italic font-serif font-normal text-transparent bg-clip-text bg-gradient-to-r from-sky-200 via-blue-100 to-white">
          powered by AI
        </span>
      </h1>

      {/* Description */}
      <p className="mt-4 max-w-xl text-sm sm:text-base text-blue-100/80 leading-relaxed font-normal">
        One engine for dynamic graph discovery, autonomous multi-hop Cypher reasoning,
        and 100% verified evidence provenance. Ask questions in natural language — explore
        insights visually.
      </p>

      {/* Call to Action Buttons */}
      <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3.5 w-full max-w-md">
        {/* Primary Launch AI Chatbot Button */}
        <button
          onClick={handlePrimaryClick}
          className="w-full sm:w-auto flex items-center justify-center gap-2.5 px-6 py-3 rounded-xl text-sm font-semibold text-white bg-[#1678ef] hover:bg-[#1264c9] shadow-sm hover:shadow-md transition cursor-pointer"
        >
          <Sparkles className="w-4 h-4 text-sky-200" />
          <span>Launch AI Chatbot</span>
          <ArrowRight className="w-4 h-4" />
        </button>

        {/* Secondary Import Dataset Button */}
        <button
          onClick={onOpenImport}
          className="w-full sm:w-auto flex items-center justify-center gap-2 px-5 py-3 rounded-xl text-sm font-semibold text-white/90 hover:text-white bg-white/10 hover:bg-white/15 border border-white/20 transition cursor-pointer"
        >
          <Upload className="w-4 h-4 text-sky-300" />
          <span>Import Dataset</span>
        </button>
      </div>

      <p className="mt-4 text-xs text-blue-200/60 flex items-center gap-1.5">
        <ShieldCheck className="w-3.5 h-3.5 text-sky-300" />
        <span>Read-Only Cypher Guardrails · Schema-Aware Multi-Domain Traversal</span>
      </p>
    </div>
  );
}

