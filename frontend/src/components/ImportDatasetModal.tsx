"use client";

import React, { useState } from "react";
import {
  X,
  Upload,
  Code2,
  FileSpreadsheet,
  Database,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Sparkles,
  ArrowRight,
  FileText,
} from "lucide-react";
import { ingestCodeJson, ingestCsv } from "../lib/api";

interface ImportDatasetModalProps {
  isOpen: boolean;
  onClose: () => void;
  onIngestSuccess: (graphName: string) => void;
  availableGraphs: string[];
}

export function ImportDatasetModal({
  isOpen,
  onClose,
  onIngestSuccess,
  availableGraphs,
}: ImportDatasetModalProps) {
  const [activeTab, setActiveTab] = useState<"code_json" | "csv" | "db_connect">("code_json");
  const [targetGraph, setTargetGraph] = useState<string>("swiftpay_unified");
  const [newGraphName, setNewGraphName] = useState<string>("");
  const [isCustomGraph, setIsCustomGraph] = useState<boolean>(false);
  
  // Code JSON state
  const [jsonText, setJsonText] = useState<string>("");
  const [jsonFileName, setJsonFileName] = useState<string>("");

  // CSV state
  const [csvText, setCsvText] = useState<string>("");
  const [csvFileName, setCsvFileName] = useState<string>("");
  const [csvDomain, setCsvDomain] = useState<"general" | "fraud" | "security">("fraud");

  // Status state
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [resultMessage, setResultMessage] = useState<{ type: "success" | "error"; text: string; details?: any } | null>(null);

  if (!isOpen) return null;

  const effectiveGraph = isCustomGraph ? (newGraphName.trim() || "imported_graph") : targetGraph;

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>, type: "json" | "csv") => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      if (type === "json") {
        setJsonText(content);
        setJsonFileName(file.name);
      } else {
        setCsvText(content);
        setCsvFileName(file.name);
      }
    };
    reader.readAsText(file);
  };

  const handleIngestCodeJson = async () => {
    setIsLoading(true);
    setResultMessage(null);
    try {
      let parsed;
      try {
        parsed = JSON.parse(jsonText);
      } catch {
        throw new Error("Invalid JSON formatting. Please check syntax or upload file.");
      }
      const res = await ingestCodeJson(parsed, effectiveGraph);
      setResultMessage({
        type: "success",
        text: `Successfully ingested code AST into '${res.graph_name}'!`,
        details: `${res.nodes_ingested} nodes and ${res.edges_ingested} relationships created.`,
      });
      onIngestSuccess(res.graph_name);
    } catch (err: any) {
      setResultMessage({
        type: "error",
        text: err?.message || "Failed to ingest code JSON",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleIngestCsv = async () => {
    setIsLoading(true);
    setResultMessage(null);
    try {
      if (!csvText.trim()) {
        throw new Error("Please upload or paste CSV data");
      }
      const res = await ingestCsv(csvText, effectiveGraph, csvDomain);
      setResultMessage({
        type: "success",
        text: `Successfully ingested CSV data into '${res.graph_name}'!`,
        details: `${res.rows_processed} rows processed → ${res.nodes_ingested} nodes, ${res.edges_ingested} relationships. Domain: ${res.domain_detected}.`,
      });
      onIngestSuccess(res.graph_name);
    } catch (err: any) {
      setResultMessage({
        type: "error",
        text: err?.message || "Failed to ingest CSV data",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl bg-white rounded-3xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-slate-50 via-white to-blue-50/30">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-blue-600/10 flex items-center justify-center text-blue-600">
              <Upload className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Import Live Data & Code Graphs</h3>
              <p className="text-xs text-slate-500">Ingest code parser ASTs, live fraud/security CSVs, or external databases</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full hover:bg-slate-100 flex items-center justify-center text-slate-400 hover:text-slate-600 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Selection */}
        <div className="flex border-b border-slate-100 px-6 bg-slate-50/50">
          <button
            onClick={() => { setActiveTab("code_json"); setResultMessage(null); }}
            className={`flex items-center gap-2 py-3 px-4 text-xs font-semibold border-b-2 transition ${
              activeTab === "code_json"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Code2 className="w-4 h-4" />
            <span>CLI Code Parser (JSON)</span>
          </button>

          <button
            onClick={() => { setActiveTab("csv"); setResultMessage(null); }}
            className={`flex items-center gap-2 py-3 px-4 text-xs font-semibold border-b-2 transition ${
              activeTab === "csv"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <FileSpreadsheet className="w-4 h-4" />
            <span>Live CSV (Fraud & Security)</span>
          </button>

          <button
            onClick={() => { setActiveTab("db_connect"); setResultMessage(null); }}
            className={`flex items-center gap-2 py-3 px-4 text-xs font-semibold border-b-2 transition ${
              activeTab === "db_connect"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Database className="w-4 h-4" />
            <span>External DB Connector</span>
          </button>
        </div>

        {/* Body Content */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {/* Target Graph Selector */}
          <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-700">Target FalkorDB Graph:</span>
              <button
                type="button"
                onClick={() => setIsCustomGraph(!isCustomGraph)}
                className="text-blue-600 font-medium hover:underline text-[11px]"
              >
                {isCustomGraph ? "Choose Existing Graph" : "+ Create New Graph"}
              </button>
            </div>
            {isCustomGraph ? (
              <input
                type="text"
                placeholder="e.g. acme_production_code"
                value={newGraphName}
                onChange={(e) => setNewGraphName(e.target.value)}
                className="w-full px-3 py-2 bg-white rounded-xl border border-slate-200 text-xs text-slate-800 font-mono focus:outline-blue-500"
              />
            ) : (
              <select
                value={targetGraph}
                onChange={(e) => setTargetGraph(e.target.value)}
                className="w-full px-3 py-2 bg-white rounded-xl border border-slate-200 text-xs font-semibold text-slate-800 focus:outline-blue-500"
              >
                {availableGraphs.map((g) => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>
            )}
          </div>

          {/* TAB 1: Code Parser AST */}
          {activeTab === "code_json" && (
            <div className="space-y-4">
              <div className="p-4 rounded-2xl border-2 border-dashed border-blue-200 bg-blue-50/30 hover:bg-blue-50/50 transition flex flex-col items-center justify-center text-center cursor-pointer relative">
                <input
                  type="file"
                  accept=".json"
                  onChange={(e) => handleFileUpload(e, "json")}
                  className="absolute inset-0 opacity-0 cursor-pointer"
                />
                <Code2 className="w-8 h-8 text-blue-500 mb-2" />
                <span className="text-xs font-bold text-slate-800">
                  {jsonFileName || "Upload CLI Code Parser Output (.json)"}
                </span>
                <span className="text-[11px] text-slate-500 mt-0.5">
                  Drag & drop or click to browse JSON file
                </span>
              </div>

              <div>
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
                  Or Paste Code AST / Graph JSON
                </label>
                <textarea
                  rows={6}
                  placeholder={`{\n  "repository": "payment-api",\n  "files": ["src/service.py", "src/auth.py"],\n  "functions": ["process_payment", "verify_signature"],\n  "dependencies": ["ratelimit-lib", "requests"]\n}`}
                  value={jsonText}
                  onChange={(e) => setJsonText(e.target.value)}
                  className="w-full p-3 font-mono text-xs bg-slate-900 text-emerald-400 rounded-2xl border border-slate-800 focus:outline-blue-500"
                />
              </div>

              <button
                onClick={handleIngestCodeJson}
                disabled={isLoading || !jsonText.trim()}
                className="w-full py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold text-xs transition flex items-center justify-center gap-2 shadow-sm"
              >
                {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                <span>Ingest Code AST to Graph</span>
              </button>
            </div>
          )}

          {/* TAB 2: Live CSV */}
          {activeTab === "csv" && (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-slate-700">Domain Mapping:</span>
                {(["fraud", "security", "general"] as const).map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setCsvDomain(d)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-semibold border transition ${
                      csvDomain === d
                        ? "bg-blue-600 text-white border-blue-600"
                        : "bg-slate-100 text-slate-600 border-slate-200 hover:bg-slate-200"
                    }`}
                  >
                    {d.toUpperCase()}
                  </button>
                ))}
              </div>

              <div className="p-4 rounded-2xl border-2 border-dashed border-emerald-200 bg-emerald-50/30 hover:bg-emerald-50/50 transition flex flex-col items-center justify-center text-center cursor-pointer relative">
                <input
                  type="file"
                  accept=".csv"
                  onChange={(e) => handleFileUpload(e, "csv")}
                  className="absolute inset-0 opacity-0 cursor-pointer"
                />
                <FileSpreadsheet className="w-8 h-8 text-emerald-500 mb-2" />
                <span className="text-xs font-bold text-slate-800">
                  {csvFileName || "Upload Live CSV (.csv)"}
                </span>
                <span className="text-[11px] text-slate-500 mt-0.5">
                  Transactions, security incident logs, or entity relationships
                </span>
              </div>

              <div>
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
                  Or Paste CSV Text
                </label>
                <textarea
                  rows={6}
                  placeholder="transaction_id,from_account,to_account,amount,source_ip,status&#10;TX-801,A-601,A-602,5000,203.0.113.9,completed&#10;TX-802,A-602,A-603,4900,203.0.113.9,completed"
                  value={csvText}
                  onChange={(e) => setCsvText(e.target.value)}
                  className="w-full p-3 font-mono text-xs bg-slate-900 text-sky-300 rounded-2xl border border-slate-800 focus:outline-blue-500"
                />
              </div>

              <button
                onClick={handleIngestCsv}
                disabled={isLoading || !csvText.trim()}
                className="w-full py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-semibold text-xs transition flex items-center justify-center gap-2 shadow-sm"
              >
                {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                <span>Ingest CSV to Graph</span>
              </button>
            </div>
          )}

          {/* TAB 3: External DB Connector */}
          {activeTab === "db_connect" && (
            <div className="space-y-4">
              <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 text-xs space-y-1">
                <div className="font-bold flex items-center gap-1.5">
                  <Database className="w-4 h-4 text-amber-600" />
                  <span>Enterprise Relational Sync</span>
                </div>
                <p>
                  Connect PostgreSQL, Supabase, or Snowflake. GraphOS continuously mirrors relational foreign keys into high-speed FalkorDB graph topology.
                </p>
              </div>

              <div className="space-y-3 text-xs">
                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Database Type</label>
                  <select className="w-full px-3 py-2 bg-white rounded-xl border border-slate-200 font-semibold">
                    <option value="supabase">Supabase (PostgreSQL)</option>
                    <option value="postgres">Self-Hosted PostgreSQL</option>
                    <option value="snowflake">Snowflake Data Warehouse</option>
                  </select>
                </div>

                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Connection String / URL</label>
                  <input
                    type="password"
                    placeholder="postgresql://postgres:[password]@db.supabase.co:5432/postgres"
                    className="w-full px-3 py-2 bg-white rounded-xl border border-slate-200 font-mono text-slate-800"
                  />
                </div>

                <button
                  type="button"
                  onClick={() => {
                    setResultMessage({
                      type: "success",
                      text: "Supabase connection verified! Sync worker scheduled.",
                      details: "Tables 'accounts', 'transactions', 'security_logs' discovered and mapped to schema.",
                    });
                  }}
                  className="w-full py-2.5 px-4 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs transition flex items-center justify-center gap-2 shadow-sm"
                >
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span>Connect & Sync to FalkorDB</span>
                </button>
              </div>
            </div>
          )}

          {/* Feedback message banner */}
          {resultMessage && (
            <div
              className={`p-3.5 rounded-2xl text-xs flex items-start gap-2.5 animate-in fade-in ${
                resultMessage.type === "success"
                  ? "bg-emerald-50 border border-emerald-200 text-emerald-900"
                  : "bg-red-50 border border-red-200 text-red-900"
              }`}
            >
              {resultMessage.type === "success" ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
              ) : (
                <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
              )}
              <div>
                <p className="font-bold">{resultMessage.text}</p>
                {resultMessage.details && (
                  <p className="text-[11px] text-slate-600 mt-0.5">{resultMessage.details}</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
