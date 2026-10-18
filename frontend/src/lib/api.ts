import {
  HealthStatus,
  GraphSchemaProfile,
  InvestigationResult,
  InvestigationEvent,
} from "../types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function getHealth(): Promise<HealthStatus | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/health`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function getAvailableGraphs(): Promise<{ graphs: string[]; active_graph: string } | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/graphs`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function getSchema(tenantGraph?: string): Promise<GraphSchemaProfile | null> {
  try {
    const url = tenantGraph
      ? `${API_BASE_URL}/api/schema?tenant_graph=${encodeURIComponent(tenantGraph)}`
      : `${API_BASE_URL}/api/schema`;
    const res = await fetch(url, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.schema || null;
  } catch {
    return null;
  }
}

export async function getGraphPreview(tenantGraph?: string): Promise<{ graph_name: string; entities: Record<string, any>; edges: any[] } | null> {
  try {
    const url = tenantGraph
      ? `${API_BASE_URL}/api/graph/preview?tenant_graph=${encodeURIComponent(tenantGraph)}`
      : `${API_BASE_URL}/api/graph/preview`;
    const res = await fetch(url);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function getDemoScenario(scenario: string): Promise<InvestigationResult> {
  const res = await fetch(`${API_BASE_URL}/api/demo/${scenario}`);
  if (!res.ok) {
    throw new Error(`Failed to load scenario: ${res.statusText}`);
  }
  return await res.json();
}

export async function executeInvestigationStream(
  objective: string,
  mode: "live" | "demo",
  onEvent: (event: InvestigationEvent) => void,
  tenantGraph?: string,
  signal?: AbortSignal
): Promise<InvestigationResult> {
  // Live SSE streaming directly from backend
  try {
    const res = await fetch(`${API_BASE_URL}/api/investigate/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ objective, mode: "live", tenant_graph: tenantGraph }),
      signal,
    });

    if (!res.ok) {
      throw new Error(`Server returned ${res.status}: ${res.statusText}`);
    }

    const reader = res.body?.getReader();
    if (!reader) {
      throw new Error("Streaming reader not supported in current environment.");
    }

    const decoder = new TextDecoder();
    let buffer = "";
    let finalResult: InvestigationResult | null = null;

    while (true) {
      if (signal?.aborted) {
        try {
          await reader.cancel();
        } catch {}
        break;
      }

      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || "";

      for (const block of lines) {
        const line = block.trim();
        if (line.startsWith("data:")) {
          const rawData = line.slice(5).trim();
          try {
            const ev: InvestigationEvent = JSON.parse(rawData);
            onEvent(ev);
            if (ev.type === "complete" && ev.metadata) {
              finalResult = ev.metadata as InvestigationResult;
            }
          } catch {
            // Ignore partial parse errors
          }
        }
      }
    }

    if (signal?.aborted) {
      return {
        objective,
        success: false,
        final_answer: `### ⏹️ Investigation Stopped\n\nThe investigation was cancelled by user request.`,
        evidence_summary: {
          total_entities_verified: 0,
          unique_entities_count: 0,
          total_edges_inspected: 0,
          total_relationships_count: 0,
          total_paths_established: 0,
          duplicate_records_detected: 0,
          provenance_verification_rate: 0,
          entities: {},
          key_paths: [],
          unresolved_gaps: ["Cancelled by user"],
        },
        steps: [],
        total_iterations: 0,
        total_tool_calls: 0,
        duration_seconds: 0,
      };
    }

    if (finalResult) {
      return finalResult;
    }

    // Fallback sync request if complete event didn't bundle full object
    const syncRes = await fetch(`${API_BASE_URL}/api/investigate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ objective, mode: "live", tenant_graph: tenantGraph || "ALL_GRAPHS" }),
      signal,
    });
    return await syncRes.json();
  } catch (err: any) {
    if (err?.name === "AbortError" || signal?.aborted) {
      onEvent({
        type: "error",
        iteration: 0,
        message: "Investigation stopped by user.",
        timestamp: new Date().toISOString(),
      });
      return {
        objective,
        success: false,
        final_answer: `### ⏹️ Investigation Stopped\n\nThe investigation was cancelled by user request.`,
        evidence_summary: {
          total_entities_verified: 0,
          unique_entities_count: 0,
          total_edges_inspected: 0,
          total_relationships_count: 0,
          total_paths_established: 0,
          duplicate_records_detected: 0,
          provenance_verification_rate: 0,
          entities: {},
          key_paths: [],
          unresolved_gaps: ["Cancelled by user"],
        },
        steps: [],
        total_iterations: 0,
        total_tool_calls: 0,
        duration_seconds: 0,
      };
    }

    const errorMsg = err?.message || "Connection refused to backend API.";
    onEvent({
      type: "error",
      iteration: 0,
      message: `Backend error: ${errorMsg}. Please ensure the server is running on ${API_BASE_URL}.`,
      timestamp: new Date().toISOString(),
    });
    return {
      objective,
      success: false,
      final_answer: `### ❌ Investigation Failed\n\n**Error:** ${errorMsg}\n\nCould not reach the backend agent service at \`${API_BASE_URL}\`. Please verify that the backend is running.`,
      evidence_summary: {
        total_entities_verified: 0,
        unique_entities_count: 0,
        total_edges_inspected: 0,
        total_relationships_count: 0,
        total_paths_established: 0,
        duplicate_records_detected: 0,
        provenance_verification_rate: 0,
        entities: {},
        key_paths: [],
        unresolved_gaps: [errorMsg],
      },
      steps: [],
      total_iterations: 0,
      total_tool_calls: 0,
      duration_seconds: 0,
    };
  }
}

export async function ingestCodeJson(
  data: any,
  graphName: string = "graphos_dev"
): Promise<{ status: string; graph_name: string; nodes_ingested: number; edges_ingested: number }> {
  const res = await fetch(`${API_BASE_URL}/api/ingest/code-json`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ graph_name: graphName, data }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Ingestion failed" }));
    throw new Error(err.detail || "Failed to ingest code AST JSON");
  }
  return await res.json();
}

export async function ingestCsv(
  csvText: string,
  graphName: string = "swiftpay_unified",
  domain: string = "general"
): Promise<{ status: string; graph_name: string; rows_processed: number; domain_detected: string; nodes_ingested: number; edges_ingested: number }> {
  const res = await fetch(`${API_BASE_URL}/api/ingest/csv`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ graph_name: graphName, csv_text: csvText, domain }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "CSV ingestion failed" }));
    throw new Error(err.detail || "Failed to ingest CSV");
  }
  return await res.json();
}

export async function approveRemediation(
  actionType: string,
  targetId: string,
  rationale: string,
  tenantGraph?: string
): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/remediation/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action_type: actionType,
      target_id: targetId,
      rationale,
      tenant_graph: tenantGraph,
    }),
  });
  if (!res.ok) {
    throw new Error("Failed to approve remediation action");
  }
  return await res.json();
}

export const LOCAL_DEMO_FIXTURES: Record<string, InvestigationResult> = {};
