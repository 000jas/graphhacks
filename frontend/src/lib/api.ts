import {
  HealthStatus,
  GraphSchemaProfile,
  InvestigationResult,
  InvestigationEvent,
  User,
  ConversationSummary,
  ConversationDetail,
} from "../types";

const RENDER_PROD_URL = "https://graphhacks-s5ln.onrender.com";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined" && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1"
    ? RENDER_PROD_URL
    : process.env.NODE_ENV === "production"
    ? RENDER_PROD_URL
    : "http://localhost:8000")
).replace(/\/+$/, "");

export function getAuthHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { ...extra };
  if (typeof window !== "undefined") {
    try {
      const token = localStorage.getItem("graphos_session_token");
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
    } catch {
      // ignore
    }
  }
  return headers;
}

export async function getHealth(): Promise<HealthStatus | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/health`, {
      method: "GET",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function getAvailableGraphs(): Promise<{ graphs: string[]; active_graph: string } | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/graphs`, {
      credentials: "include",
    });
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
      credentials: "include",
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
    const res = await fetch(url, {
      credentials: "include",
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function getDemoScenario(scenario: string): Promise<InvestigationResult> {
  const res = await fetch(`${API_BASE_URL}/api/demo/${scenario}`, {
    credentials: "include",
  });
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
  signal?: AbortSignal,
  conversationId?: string,
  onConversationAssigned?: (convId: string) => void
): Promise<InvestigationResult> {
  // Live SSE streaming directly from backend
  try {
    const res = await fetch(`${API_BASE_URL}/api/investigate/stream`, {
      method: "POST",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({
        objective,
        mode: "live",
        tenant_graph: tenantGraph,
        conversation_id: conversationId,
      }),
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
            if ((ev as any).type === "conversation_assigned" && ev.metadata?.conversation_id) {
              onConversationAssigned?.(ev.metadata.conversation_id);
            }
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

    throw new Error("Investigation stream ended without final synthesis result.");
  } catch (err: any) {
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
    const errorMsg = err?.message || "Unknown streaming error";
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
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    credentials: "include",
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
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    credentials: "include",
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
  tenantGraph?: string,
  params?: Record<string, any>
): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/remediation/approve`, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    credentials: "include",
    body: JSON.stringify({
      action_type: actionType,
      target_id: targetId,
      rationale,
      tenant_graph: tenantGraph,
      params: params || {},
    }),
  });
  if (!res.ok) {
    throw new Error("Failed to approve remediation action");
  }
  return await res.json();
}

export async function planActionLifecycle(
  objective: string,
  targetId?: string,
  actionType?: string,
  params?: Record<string, any>,
  rationale?: string,
  tenantGraph?: string
): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/actions/plan`, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    credentials: "include",
    body: JSON.stringify({
      objective,
      target_id: targetId,
      action_type: actionType,
      params: params || {},
      rationale,
      tenant_graph: tenantGraph,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Action planning failed" }));
    throw new Error(err.detail || "Failed to plan action lifecycle");
  }
  return await res.json();
}

export async function executeActionLifecycle(
  proposalId: string,
  approvalToken: string,
  actionType?: string,
  targetId?: string,
  approvedBy?: string,
  tenantGraph?: string
): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/actions/execute`, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    credentials: "include",
    body: JSON.stringify({
      proposal_id: proposalId,
      approval_token: approvalToken,
      action_type: actionType,
      target_id: targetId,
      approved_by: approvedBy || "analyst",
      tenant_graph: tenantGraph,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Action execution failed" }));
    throw new Error(err.detail || "Failed to execute action lifecycle");
  }
  return await res.json();
}

export async function validateActionOutcome(
  actionType: string,
  targetId: string,
  params?: Record<string, any>,
  tenantGraph?: string
): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/actions/validate`, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    credentials: "include",
    body: JSON.stringify({
      action_type: actionType,
      target_id: targetId,
      params: params || {},
      tenant_graph: tenantGraph,
    }),
  });
  if (!res.ok) {
    throw new Error("Failed to validate action outcome");
  }
  return await res.json();
}

export async function getActionAuditTrail(
  proposalId?: string,
  targetId?: string,
  tenantGraph?: string,
  limit: number = 20
): Promise<any> {
  const params = new URLSearchParams();
  if (proposalId) params.append("proposal_id", proposalId);
  if (targetId) params.append("target_id", targetId);
  if (tenantGraph) params.append("tenant_graph", tenantGraph);
  params.append("limit", limit.toString());

  const res = await fetch(`${API_BASE_URL}/api/actions/audit-trail?${params.toString()}`, {
    method: "GET",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    credentials: "include",
  });
  if (!res.ok) {
    throw new Error("Failed to fetch action audit trail");
  }
  return await res.json();
}

// ============================================================================
// Authentication & User Session API Calls
// ============================================================================

export async function getMe(): Promise<User | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/auth/me`, {
      method: "GET",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.authenticated && data.user ? data.user : null;
  } catch {
    return null;
  }
}

export async function signupUser(
  name: string,
  email: string,
  password: string
): Promise<{ user: User; session_token: string }> {
  const res = await fetch(`${API_BASE_URL}/api/auth/signup`, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    credentials: "include",
    body: JSON.stringify({ name, email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Sign up failed" }));
    throw new Error(err.detail || "Sign up failed");
  }
  const data = await res.json();
  if (typeof window !== "undefined" && data?.session_token) {
    try {
      localStorage.setItem("graphos_session_token", data.session_token);
    } catch {}
  }
  return data;
}

export async function loginUser(
  email: string,
  password?: string
): Promise<{ user: User; session_token: string }> {
  const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    credentials: "include",
    body: JSON.stringify({ email, password: password || undefined }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Login failed" }));
    throw new Error(err.detail || "Account not found with this email. Please check your email or sign up.");
  }
  const data = await res.json();
  if (typeof window !== "undefined" && data?.session_token) {
    try {
      localStorage.setItem("graphos_session_token", data.session_token);
    } catch {}
  }
  return data;
}

export async function logoutUser(): Promise<void> {
  if (typeof window !== "undefined") {
    try {
      localStorage.removeItem("graphos_session_token");
    } catch {}
  }
  await fetch(`${API_BASE_URL}/api/auth/logout`, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    credentials: "include",
  }).catch(() => {});
}

// ============================================================================
// Persistent Chat History API Calls (FalkorDB `graphos_history`)
// ============================================================================

export async function getConversations(): Promise<ConversationSummary[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/conversations`, {
      method: "GET",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
    });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data.conversations) ? data.conversations : [];
  } catch {
    return [];
  }
}

export async function createConversation(
  title: string = "New Investigation",
  graphName: string = "ALL_GRAPHS"
): Promise<ConversationSummary | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/conversations`, {
      method: "POST",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify({ title, graph_name: graphName }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.conversation || null;
  } catch {
    return null;
  }
}

export async function getConversation(conversationId: string): Promise<ConversationDetail | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/conversations/${encodeURIComponent(conversationId)}`, {
      method: "GET",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.conversation || null;
  } catch {
    return null;
  }
}

export async function deleteConversation(conversationId: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/conversations/${encodeURIComponent(conversationId)}`, {
      method: "DELETE",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      credentials: "include",
    });
    return res.ok;
  } catch {
    return false;
  }
}

export const LOCAL_DEMO_FIXTURES: Record<string, InvestigationResult> = {};
