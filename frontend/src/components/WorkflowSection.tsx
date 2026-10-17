"use client";

import React from "react";
import { Compass, Search, ShieldCheck, FileText, ArrowRight, Database, Network, Cpu } from "lucide-react";

interface WorkflowSectionProps {
  onOpenWorkspace: () => void;
}

export function WorkflowSection({ onOpenWorkspace }: WorkflowSectionProps) {
  const steps = [
    {
      num: "01",
      title: "Discover",
      heading: "Dynamic Schema Profile",
      desc: "Connects via MCP to inspect graph topology, node kinds, and relationship patterns without requiring hardcoded entity models.",
      icon: Compass,
    },
    {
      num: "02",
      title: "Investigate",
      heading: "Question-Driven Planning",
      desc: "Deconstructs natural language user objectives into targeted MCP tool calls, querying entities and traversing adjacent relationships.",
      icon: Search,
    },
    {
      num: "03",
      title: "Verify",
      heading: "Deterministic Provenance",
      desc: "Derives entity facts, edge keys, and constituent path hops directly from database responses, eliminating LLM hallucination.",
      icon: ShieldCheck,
    },
    {
      num: "04",
      title: "Explain",
      heading: "Interactive Evidence Graph",
      desc: "Synthesizes plain English findings backed by interactive subgraphs, property drawers, and verified dependency chains.",
      icon: FileText,
    },
  ];

  return (
    <section id="workflow" className="py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto border-t border-[#4370aa]/15">
      <div className="text-center max-w-3xl mx-auto mb-16">
        <span className="text-xs font-bold uppercase tracking-wider text-[#1678ef]">
          How GraphOS Operates
        </span>
        <h2 className="mt-3 text-3xl sm:text-4xl font-bold tracking-tight text-[#102f58]">
          From Natural Language to Verified Graph Paths
        </h2>
        <p className="mt-4 text-base text-[#71849e]">
          GraphOS maintains strict separation between runtime graph topology and investigation reasoning. Every conclusion is bound to verified graph records.
        </p>
      </div>

      {/* 4 Step Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {steps.map((st) => {
          const Icon = st.icon;
          return (
            <div
              key={st.num}
              className="white-glass-card rounded-3xl p-6 relative flex flex-col justify-between hover:border-[#1678ef]/40 transition group"
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <span className="text-2xl font-bold font-mono text-[#82c4ff] group-hover:text-[#1678ef] transition">
                    {st.num}
                  </span>
                  <div className="w-10 h-10 rounded-xl bg-[#eff7ff] text-[#1678ef] flex items-center justify-center">
                    <Icon className="w-5 h-5" />
                  </div>
                </div>

                <span className="text-xs font-bold uppercase tracking-wider text-[#1678ef]">
                  {st.title}
                </span>
                <h3 className="text-base font-bold text-[#102f58] mt-1 mb-2">
                  {st.heading}
                </h3>
                <p className="text-xs text-[#71849e] leading-relaxed">
                  {st.desc}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Product preview banner */}
      <div className="mt-16 rounded-3xl p-8 sm:p-12 bg-gradient-to-br from-[#0a2852] to-[#061a38] text-white shadow-2xl relative overflow-hidden flex flex-col lg:flex-row items-center justify-between gap-8">
        <div className="max-w-xl">
          <span className="px-3 py-1 rounded-full text-xs font-semibold bg-[#1678ef]/30 text-[#82c4ff] border border-[#1678ef]/50 inline-block mb-4">
            Interactive AI Investigation Workspace
          </span>
          <h3 className="text-2xl sm:text-3xl font-bold tracking-tight leading-snug">
            Ready to explore your connected data?
          </h3>
          <p className="mt-3 text-sm text-white/80 leading-relaxed">
            Launch the GraphOS Intelligence Workspace to run live or simulated graph investigations across fraud, security, and software dependencies.
          </p>
        </div>

        <button
          onClick={onOpenWorkspace}
          className="px-6 py-3.5 rounded-full text-sm font-semibold text-white bg-gradient-to-r from-[#1678ef] to-[#268cf5] hover:from-[#1b80ff] hover:to-[#389aff] shadow-lg shadow-[#1678ef]/40 transition transform hover:-translate-y-0.5 active:translate-y-0 flex items-center gap-2 shrink-0"
        >
          <span>Open Investigation Workspace</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </section>
  );
}
