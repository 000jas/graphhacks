"use client";

import React from "react";
import { Sparkles, ArrowRight, Upload, Lock, ShieldCheck, UserCheck } from "lucide-react";
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
    <div className="relative pt-6 pb-16 md:pt-10 md:pb-24 px-4 sm:px-6 lg:px-8 flex flex-col items-center text-center z-20">
      {/* Top pill badge */}
      {user ? (
        <div className="inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-white/10 border border-white/20 text-white text-xs font-medium backdrop-blur-md mb-8 shadow-sm">
          <span className="px-2 py-0.5 rounded-full bg-emerald-400 text-[#061a38] text-[10px] font-extrabold uppercase tracking-wider flex items-center gap-1">
            <UserCheck className="w-3 h-3" /> Logged In
          </span>
          <span className="text-white/90">
            Welcome back, <strong className="text-[#38bdf8]">{user.name}</strong> · Chatbot Ready
          </span>
        </div>
      ) : (
        <div className="inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-amber-400/15 border border-amber-400/40 text-white text-xs font-medium backdrop-blur-md mb-8 shadow-md shadow-amber-950/20">
          <span className="px-2 py-0.5 rounded-full bg-amber-400 text-[#061a38] text-[10px] font-extrabold uppercase tracking-wider flex items-center gap-1">
            <Lock className="w-3 h-3" /> Step 1: Sign In
          </span>
          <span className="text-amber-100 font-semibold">
            First login required to launch AI investigations & access graphs
          </span>
        </div>
      )}

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

      {/* Prominent Login Importance Callout Banner when logged out */}
      {!user && (
        <div className="mt-8 max-w-xl mx-auto w-full px-5 py-3.5 rounded-2xl bg-gradient-to-r from-blue-950/80 via-[#0a2347]/90 to-blue-950/80 border border-[#38bdf8]/50 backdrop-blur-md text-left flex flex-col sm:flex-row items-center justify-between gap-4 shadow-xl shadow-blue-950/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#1678ef] to-[#38bdf8] flex items-center justify-center text-white shrink-0 shadow-md">
              <Lock className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-extrabold text-white tracking-wide">
                  Sign In Required to Launch Chat
                </span>
                <span className="text-[10px] font-black uppercase tracking-wider bg-amber-400 text-[#0b2447] px-2 py-0.5 rounded-full">
                  Important
                </span>
              </div>
              <p className="text-[11px] text-blue-200/90 leading-tight mt-0.5">
                First login is required to access your dedicated graph workspace, run AI investigations, and preserve chat history.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onOpenAuth || handlePrimaryClick}
            className="w-full sm:w-auto px-4 py-2 rounded-xl text-xs font-bold text-[#061a38] bg-amber-400 hover:bg-amber-300 transition shadow-md cursor-pointer shrink-0 text-center"
          >
            Sign In / Register
          </button>
        </div>
      )}

      {/* Prominent Call to Action Buttons */}
      <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4 w-full max-w-md">
        {/* Highlighted Primary Button */}
        <button
          onClick={handlePrimaryClick}
          className="w-full sm:w-auto flex items-center justify-center gap-3 px-8 py-4 rounded-2xl text-base font-bold text-white bg-gradient-to-r from-[#1678ef] via-[#2563eb] to-[#0ea5e9] hover:brightness-110 shadow-2xl shadow-blue-500/40 hover:shadow-blue-500/60 transition transform hover:-translate-y-0.5 active:translate-y-0 cursor-pointer border border-white/20"
        >
          {user ? (
            <>
              <Sparkles className="w-5 h-5 text-sky-200" />
              <span>Launch AI Chatbot</span>
              <ArrowRight className="w-5 h-5" />
            </>
          ) : (
            <>
              <Lock className="w-5 h-5 text-amber-300" />
              <span>Sign In to Launch Chatbot</span>
              <ArrowRight className="w-5 h-5" />
            </>
          )}
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

      {!user && (
        <p className="mt-3 text-xs text-blue-200/70 flex items-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-[#38bdf8]" />
          <span>Secure Argon2 authentication · Isolated tenant graph memory</span>
        </p>
      )}
    </div>
  );
}
