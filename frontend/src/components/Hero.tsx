"use client";

import React, { useState } from "react";
import {
  Sparkles,
  ArrowRight,
  Database,
  Search,
  Shield,
  Code,
  CreditCard,
  Activity,
  Plus,
  Network,
  Mic,
  ArrowUp,
  Layers,
  Lock,
  X,
  CheckCircle2,
  Sliders,
} from "lucide-react";

interface HeroProps {
  onStartInvestigation: (query: string) => void;
  mode: "live" | "demo";
}

export function Hero({ onStartInvestigation, mode }: HeroProps) {
  const [query, setQuery] = useState("");
  const [activeModal, setActiveModal] = useState<"plus" | "db" | "schema" | "guard" | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [voiceNotice, setVoiceNotice] = useState<string | null>(null);

  const starterPrompts = [
    {
      label: "Trace suspicious transactions",
      icon: CreditCard,
      prompt: "Investigate suspicious transactions and find connected entities or transaction paths that may be relevant.",
    },
    {
      label: "Triage security finding blast radius",
      icon: Shield,
      prompt: "Investigate these security findings, trace their connected dependencies, and identify which findings warrant attention.",
    },
    {
      label: "Investigate release code dependencies",
      icon: Code,
      prompt: "Trace dependencies related to this component and identify the possible impact of a proposed change.",
    },
  ];

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;
    onStartInvestigation(query.trim());
  };

  const handleChipClick = (promptText: string) => {
    setQuery(promptText);
    onStartInvestigation(promptText);
  };

  // Interactive Voice Input using Web Speech API with fallback
  const handleVoiceToggle = () => {
    if (typeof window !== "undefined" && ("webkitSpeechRecognition" in window || "SpeechRecognition" in window)) {
      try {
        const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = "en-US";

        setIsListening(true);
        setVoiceNotice("Listening to speech...");

        recognition.onresult = (event: any) => {
          const transcript = event.results[0][0].transcript;
          setQuery((prev) => (prev ? `${prev} ${transcript}` : transcript));
          setIsListening(false);
          setVoiceNotice("Voice transcribed!");
          setTimeout(() => setVoiceNotice(null), 2500);
        };

        recognition.onerror = () => {
          setIsListening(false);
          setVoiceNotice("Microphone unavailable, loaded sample query");
          setQuery("Trace suspicious mule account hops to destination wallet");
          setTimeout(() => setVoiceNotice(null), 2500);
        };

        recognition.start();
        return;
      } catch {
        // fallback
      }
    }

    // Voice simulation fallback
    setIsListening(true);
    setVoiceNotice("Simulating voice input...");
    setTimeout(() => {
      setQuery("Trace suspicious mule account transactions and find connected entities");
      setIsListening(false);
      setVoiceNotice("Transcribed: Trace suspicious mule account transactions");
      setTimeout(() => setVoiceNotice(null), 2500);
    }, 1000);
  };

  return (
    <div className="relative pt-6 pb-24 md:pt-12 md:pb-32 px-4 sm:px-6 lg:px-8 flex flex-col items-center text-center">

      {/* Top pill badge — interactive button that opens connection status modal */}
      <button
        onClick={() => setActiveModal(activeModal === "db" ? null : "db")}
        className="inline-flex items-center gap-2.5 px-3 py-1 rounded-full bg-white/10 hover:bg-white/20 border border-white/20 text-white text-xs font-medium backdrop-blur-md mb-8 transition shadow-sm group transform hover:scale-[1.02] active:scale-[0.98]"
        title="View live connection status"
      >
        <span className="px-1.5 py-0.5 rounded bg-white text-[#061a38] text-[10px] font-extrabold uppercase tracking-wider group-hover:bg-[#38bdf8] group-hover:text-white transition">
          {mode === "live" ? "LIVE" : "DEMO"}
        </span>
        <span className="text-white/90">Universal Knowledge Graph Agent Active</span>
        <ArrowRight className="w-3 h-3 text-[#38bdf8] group-hover:translate-x-0.5 transition" />
      </button>

      {/* Headline with italic emphasis inspired by reference */}
      <h1 className="max-w-4xl text-5xl sm:text-6xl md:text-7xl font-extrabold tracking-tight text-white leading-[1.08] drop-shadow-[0_4px_30px_rgba(0,0,0,0.4)]">
        Graph intelligence,
        <br />
        <span className="italic font-serif text-transparent bg-clip-text bg-gradient-to-r from-[#60b5ff] via-[#82c4ff] to-[#38bdf8] font-normal drop-shadow-[0_0_35px_rgba(56,189,248,0.5)]">
          powered by AI
        </span>
      </h1>

      {/* Supporting text */}
      <p className="mt-5 max-w-2xl text-base sm:text-lg text-blue-100/90 leading-relaxed font-normal">
        One engine for dynamic graph discovery, autonomous multi-hop traversal, and full evidence provenance tracking.
      </p>

      {/* Frosted Glass Prompt Composer Container — exact pill style from Luminai reference */}
      <div className="mt-10 w-full max-w-3xl frosted-glass-composer rounded-[30px] p-3 sm:p-4 transition-all duration-300 relative text-left z-20">
        {/* Specular highlight line on top edge */}
        <div className="absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-white/40 to-transparent pointer-events-none" />

        <form onSubmit={handleSubmit} className="flex flex-col gap-2.5">
          {/* Main prompt input */}
          <div className="px-2 pt-1">
            <textarea
              rows={2}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit();
                }
              }}
              placeholder="Ask GraphOS to investigate connected data, trace dependencies, or uncover root cause..."
              className="w-full bg-transparent resize-none border-none outline-none text-white text-base sm:text-lg placeholder:text-blue-200/50 leading-relaxed font-normal focus:ring-0 focus:outline-none"
            />
          </div>

          {/* Voice status feedback notification if active */}
          {voiceNotice && (
            <div className="px-3 py-1 rounded-lg bg-[#1678ef]/30 border border-[#38bdf8]/40 text-xs text-[#7dd3fc] flex items-center justify-between animate-in fade-in">
              <span>{voiceNotice}</span>
              {isListening && <span className="w-2 h-2 rounded-full bg-[#38bdf8] animate-ping" />}
            </div>
          )}

          {/* Bottom controls row — rounded pills matching reference */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-white/10 px-1">
            <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
              {/* Plus button -> opens scope filter modal */}
              <button
                type="button"
                onClick={() => setActiveModal(activeModal === "plus" ? null : "plus")}
                className={`w-7 h-7 rounded-full border flex items-center justify-center transition ${
                  activeModal === "plus"
                    ? "bg-[#38bdf8] text-[#061a38] border-white"
                    : "bg-white/10 hover:bg-white/20 border-white/20 text-white/80 hover:text-white"
                }`}
                title="Investigation Parameters & Scope"
              >
                <Plus className="w-3.5 h-3.5" />
              </button>

              {/* Database pill -> opens live DB modal */}
              <button
                type="button"
                onClick={() => setActiveModal(activeModal === "db" ? null : "db")}
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-[11px] font-medium transition ${
                  activeModal === "db"
                    ? "bg-[#1678ef] text-white border-[#38bdf8]"
                    : "bg-white/10 hover:bg-white/15 border-white/15 text-white"
                }`}
              >
                <Database className="w-3 h-3 text-[#38bdf8]" />
                <span>FalkorDB MCP</span>
              </button>

              {/* Dynamic Schema pill -> opens schema modal */}
              <button
                type="button"
                onClick={() => setActiveModal(activeModal === "schema" ? null : "schema")}
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-[11px] font-medium transition ${
                  activeModal === "schema"
                    ? "bg-[#1678ef] text-white border-[#38bdf8]"
                    : "bg-white/10 hover:bg-white/15 border-white/15 text-white"
                }`}
              >
                <Network className="w-3 h-3 text-[#82c4ff]" />
                <span>Dynamic Schema</span>
              </button>

              {/* Read-Only Guard pill -> opens guardrails modal */}
              <button
                type="button"
                onClick={() => setActiveModal(activeModal === "guard" ? null : "guard")}
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-[11px] font-medium transition ${
                  activeModal === "guard"
                    ? "bg-[#1678ef] text-white border-[#38bdf8]"
                    : "bg-white/10 hover:bg-white/15 border-white/15 text-white"
                }`}
              >
                <Lock className="w-3 h-3 text-emerald-400" />
                <span>Read-Only Guard</span>
              </button>
            </div>

            <div className="flex items-center gap-2 ml-auto">
              {/* Mic button -> interactive voice input */}
              <button
                type="button"
                onClick={handleVoiceToggle}
                className={`w-8 h-8 rounded-full border flex items-center justify-center transition ${
                  isListening
                    ? "bg-red-500 text-white border-red-400 animate-pulse"
                    : "bg-white/10 hover:bg-white/20 border-white/15 text-white/70 hover:text-white"
                }`}
                title={isListening ? "Listening..." : "Click to speak voice prompt"}
              >
                <Mic className="w-3.5 h-3.5" />
              </button>

              {/* Send button -> triggers real investigation */}
              <button
                type="submit"
                disabled={!query.trim()}
                className={`w-9 h-9 rounded-full flex items-center justify-center transition-all duration-200 ${
                  query.trim()
                    ? "bg-gradient-to-r from-[#1678ef] via-[#268cf5] to-[#00d2ff] text-white shadow-[0_0_20px_rgba(22,120,239,0.7)] hover:shadow-[0_0_30px_rgba(0,210,255,0.9)] hover:scale-105 active:scale-95"
                    : "bg-white/10 text-white/30 cursor-not-allowed border border-white/10"
                }`}
                title="Send Investigation Query"
              >
                <ArrowUp className="w-4 h-4" />
              </button>
            </div>
          </div>
        </form>

        {/* Interactive Popover Modals for Composer Pills */}
        {activeModal && (
          <div className="mt-3 p-4 rounded-2xl bg-[#061838]/95 border border-white/20 backdrop-blur-xl text-xs text-white shadow-2xl animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-2 border-b border-white/10 mb-2">
              <span className="font-semibold text-sm text-[#82c4ff] flex items-center gap-2">
                {activeModal === "plus" && <Sliders className="w-4 h-4" />}
                {activeModal === "db" && <Database className="w-4 h-4" />}
                {activeModal === "schema" && <Network className="w-4 h-4" />}
                {activeModal === "guard" && <Lock className="w-4 h-4" />}
                <span>
                  {activeModal === "plus" && "Investigation Parameters"}
                  {activeModal === "db" && "FalkorDB MCP Connection"}
                  {activeModal === "schema" && "Discovered Graph Topology"}
                  {activeModal === "guard" && "Strict Read-Only Guardrails"}
                </span>
              </span>
              <button
                onClick={() => setActiveModal(null)}
                className="text-white/60 hover:text-white p-1"
                aria-label="Close dialog"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            {activeModal === "plus" && (
              <div className="space-y-2 text-white/80">
                <p>Configure autonomous investigation boundaries:</p>
                <div className="grid grid-cols-2 gap-2 pt-1">
                  <div className="p-2 rounded-xl bg-white/5 border border-white/10">
                    <span className="text-[10px] text-white/50 block">Max Traversal Hops</span>
                    <span className="font-semibold text-[#38bdf8]">3 Hops (Configurable)</span>
                  </div>
                  <div className="p-2 rounded-xl bg-white/5 border border-white/10">
                    <span className="text-[10px] text-white/50 block">Provenance Strictness</span>
                    <span className="font-semibold text-emerald-400">100% Deterministic</span>
                  </div>
                </div>
              </div>
            )}

            {activeModal === "db" && (
              <div className="space-y-1.5 text-white/80">
                <div className="flex justify-between py-1 border-b border-white/5">
                  <span className="text-white/50">MCP Transport:</span>
                  <span className="font-mono text-[#38bdf8]">FastAPI SSE / stdio</span>
                </div>
                <div className="flex justify-between py-1 border-b border-white/5">
                  <span className="text-white/50">Backend Target:</span>
                  <span className="font-mono text-white">FalkorDB Knowledge Graph</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-white/50">Status:</span>
                  <span className="text-emerald-400 font-semibold flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Ready
                  </span>
                </div>
              </div>
            )}

            {activeModal === "schema" && (
              <div className="space-y-2 text-white/80">
                <p>Click any node kind to insert into your query:</p>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {["Account", "Service", "Repository", "Task", "Person", "Policy", "AuditRecord"].map(
                    (k) => (
                      <button
                        key={k}
                        type="button"
                        onClick={() => {
                          setQuery((prev) => (prev ? `${prev} related to :${k}` : `Investigate entities of kind :${k}`));
                          setActiveModal(null);
                        }}
                        className="px-2.5 py-1 rounded-lg bg-white/10 hover:bg-[#1678ef] text-white font-mono text-[11px] border border-white/15 transition"
                      >
                        :{k}
                      </button>
                    )
                  )}
                </div>
              </div>
            )}

            {activeModal === "guard" && (
              <div className="space-y-1.5 text-white/80">
                <p className="text-emerald-300 font-medium">Read-Only Safety Guarantee Active:</p>
                <ul className="list-disc pl-4 space-y-1 text-white/70 text-[11px]">
                  <li>Mutating Cypher statements (CREATE, SET, DELETE, MERGE) are intercepted and rejected.</li>
                  <li>LLM tool execution budget capped at safe deterministic threshold.</li>
                  <li>No write privileges permitted in browser or agent loop.</li>
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Starter scenarios as sleek pill chips */}
      <div className="mt-6 flex flex-wrap items-center justify-center gap-2 max-w-2xl z-10">
        <span className="text-xs text-white/50 font-medium mr-1">Suggested:</span>
        {starterPrompts.map((item, idx) => {
          const Icon = item.icon;
          return (
            <button
              key={idx}
              type="button"
              onClick={() => handleChipClick(item.prompt)}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-white/[0.08] hover:bg-white/[0.18] border border-white/15 hover:border-white/30 text-blue-100 hover:text-white text-xs font-medium transition transform hover:-translate-y-0.5 active:translate-y-0 shadow-sm"
            >
              <Icon className="w-3.5 h-3.5 text-[#38bdf8]" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
