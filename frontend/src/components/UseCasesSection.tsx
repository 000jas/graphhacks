"use client";

import React from "react";
import { CreditCard, Shield, Code, ArrowUpRight, CheckCircle2, GitFork, Network, Lock } from "lucide-react";

interface UseCasesSectionProps {
  onSelectPrompt: (prompt: string) => void;
}

export function UseCasesSection({ onSelectPrompt }: UseCasesSectionProps) {
  const useCases = [
    {
      id: "fraud",
      title: "Fraud & Sybil Ring Investigation",
      subtitle: "Financial Network & Transaction Graph",
      icon: CreditCard,
      accentColor: "#2563eb",
      badge: "High Velocity AML",
      prompt: "Investigate suspicious transactions and find connected entities or transaction paths that may be relevant.",
      features: [
        "Uncover 3-hop mule account dispersion rings",
        "Correlate shared device hardware fingerprints",
        "Detect Tor network egress cash-out points",
      ],
      sampleQuery: "Trace acc-mule-881 to destination wallets",
    },
    {
      id: "security",
      title: "Security Finding & Blast Radius Triage",
      subtitle: "Cloud IAM & Microservices Graph",
      icon: Shield,
      accentColor: "#dc2626",
      badge: "Critical CVE-2026-4412",
      prompt: "Investigate these security findings, trace their connected dependencies, and identify which findings warrant attention.",
      features: [
        "Trace public gateway RCE vulnerabilities",
        "Map overprivileged IAM wildcard role escalation",
        "Quantify exposed customer database stores",
      ],
      sampleQuery: "Evaluate blast radius for auth gateway CVE",
    },
    {
      id: "codebase",
      title: "Codebase & Release Bottleneck Analysis",
      subtitle: "Git, Tasks & Organizational Graph",
      icon: Code,
      accentColor: "#16a34a",
      badge: "Production Delayed",
      prompt: "Trace dependencies related to this component and identify the possible impact of a proposed change.",
      features: [
        "Isolate blocked pull requests and pending reviews",
        "Detect reviewer unavailability from HR records",
        "Evaluate governance policy for safe review reassignment",
      ],
      sampleQuery: "Find blockers for Payments October Release",
    },
  ];

  return (
    <section id="use-cases" className="py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
      <div className="text-center max-w-3xl mx-auto mb-16">
        <span className="text-xs font-bold uppercase tracking-wider text-[#1678ef]">
          One Universal Engine · Three Demonstrations
        </span>
        <h2 className="mt-3 text-3xl sm:text-4xl font-bold tracking-tight text-[#102f58]">
          Grounded Graph Intelligence Across Any Domain
        </h2>
        <p className="mt-4 text-base text-[#71849e]">
          GraphOS adapts dynamically to any FalkorDB schema via MCP. Explore these three demonstration scenarios driven by the same autonomous investigation loop.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {useCases.map((uc) => {
          const Icon = uc.icon;
          return (
            <div
              key={uc.id}
              className="white-glass-card rounded-3xl p-6 sm:p-7 flex flex-col justify-between hover:shadow-xl hover:border-[#1678ef]/40 transition-all duration-300 group"
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div
                    className="w-12 h-12 rounded-2xl flex items-center justify-center text-white shadow-md transition-transform group-hover:scale-105"
                    style={{ backgroundColor: uc.accentColor }}
                  >
                    <Icon className="w-6 h-6" />
                  </div>
                  <span className="px-3 py-1 rounded-full text-[11px] font-semibold bg-[#eff7ff] text-[#1678ef] border border-[#1678ef]/20">
                    {uc.badge}
                  </span>
                </div>

                <h3 className="text-lg font-bold text-[#102f58] group-hover:text-[#1678ef] transition">
                  {uc.title}
                </h3>
                <p className="text-xs font-semibold text-[#71849e] mt-1 mb-4">
                  {uc.subtitle}
                </p>

                <div className="space-y-2.5 mb-6 text-xs text-[#3b577d]">
                  {uc.features.map((feat, idx) => (
                    <div key={idx} className="flex items-start gap-2">
                      <CheckCircle2 className="w-4 h-4 text-[#1678ef] shrink-0 mt-0.5" />
                      <span>{feat}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div className="p-3 rounded-2xl bg-[#f6faff] border border-[#4370aa]/15 mb-4">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[#71849e]">
                    Investigation Prompt
                  </span>
                  <p className="text-xs text-[#102f58] font-medium mt-1 italic">
                    "{uc.prompt}"
                  </p>
                </div>

                <button
                  onClick={() => onSelectPrompt(uc.prompt)}
                  className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-semibold text-[#1678ef] bg-[#eff7ff] hover:bg-[#1678ef] hover:text-white border border-[#1678ef]/30 transition group-hover:shadow-md"
                >
                  <span>Launch Investigation</span>
                  <ArrowUpRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
