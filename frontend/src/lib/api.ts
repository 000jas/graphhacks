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
  try {
    const res = await fetch(`${API_BASE_URL}/api/demo/${scenario}`);
    if (res.ok) {
      return await res.json();
    }
  } catch {
    // fallback to local fixture if backend server not running
  }
  return LOCAL_DEMO_FIXTURES[scenario] || LOCAL_DEMO_FIXTURES.codebase;
}

export async function executeInvestigationStream(
  objective: string,
  mode: "live" | "demo",
  onEvent: (event: InvestigationEvent) => void,
  tenantGraph?: string
): Promise<InvestigationResult> {
  if (mode === "demo") {
    const scenarioKey = objective.toLowerCase().includes("fraud") || objective.toLowerCase().includes("transaction")
      ? "fraud"
      : objective.toLowerCase().includes("security") || objective.toLowerCase().includes("cve")
      ? "security"
      : "codebase";

    const fixture = LOCAL_DEMO_FIXTURES[scenarioKey];

    onEvent({
      type: "plan",
      iteration: 0,
      message: `[Demo Mode] Formulating graph discovery plan for ${fixture.objective.slice(0, 45)}...`,
      timestamp: new Date().toISOString(),
    });
    await new Promise((r) => setTimeout(r, 400));

    for (const step of fixture.steps) {
      onEvent({
        type: "thought",
        iteration: step.iteration,
        message: step.thought || "Analyzing graph context...",
        timestamp: new Date().toISOString(),
      });
      await new Promise((r) => setTimeout(r, 500));

      for (const tc of step.tool_calls) {
        onEvent({
          type: "tool_call",
          iteration: step.iteration,
          message: `Calling MCP tool: ${tc.function_name}`,
          metadata: { tool: tc.function_name, arguments: tc.arguments },
          timestamp: new Date().toISOString(),
        });
        await new Promise((r) => setTimeout(r, 450));

        onEvent({
          type: "tool_result",
          iteration: step.iteration,
          message: `Retrieved grounded data from ${tc.function_name}`,
          timestamp: new Date().toISOString(),
        });
        await new Promise((r) => setTimeout(r, 300));
      }
    }

    onEvent({
      type: "complete",
      iteration: fixture.total_iterations,
      message: "Investigation complete. Synthesizing evidence.",
      metadata: fixture,
      timestamp: new Date().toISOString(),
    });

    return fixture;
  }

  // Live Mode SSE streaming
  try {
    const res = await fetch(`${API_BASE_URL}/api/investigate/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ objective, mode: "live", tenant_graph: tenantGraph }),
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

    if (finalResult) {
      return finalResult;
    }

    // Fallback if complete event didn't bundle full object
    const syncRes = await fetch(`${API_BASE_URL}/api/investigate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ objective, mode: "live", tenant_graph: tenantGraph || "ALL_GRAPHS" }),
    });
    return await syncRes.json();
  } catch (err: any) {
    onEvent({
      type: "error",
      iteration: 0,
      message: `Live backend error: ${err?.message || "Connection refused"}. Switching to Demo mode preview.`,
      timestamp: new Date().toISOString(),
    });
    // Return synthetic demo result on live failure so UI never crashes
    return LOCAL_DEMO_FIXTURES.codebase;
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

export const LOCAL_DEMO_FIXTURES: Record<string, InvestigationResult> = {

  fraud: {
    objective: "Investigate suspicious transactions and find connected entities or transaction paths that may be relevant.",
    success: true,
    final_answer: `### Executive Summary: High-Risk Financial Sybil Ring Detected

Based on verified multi-hop transaction evidence across the knowledge graph, account **\`acc-mule-881\`** connects to **\`acc-target-902\`** through a layered 3-hop transfer chain and a shared hardware fingerprint:

1. **Transaction Laundering Chain**:
   - \`acc-mule-881\` (*Flagged: Suspicious High-Velocity*) transferred **$48,500 USD** to \`acc-intermediary-440\`.
   - \`acc-intermediary-440\` subsequently dispersed **$47,900 USD** to destination \`acc-target-902\` within 4 minutes.
2. **Device Hardware Fingerprint Association**:
   - Both \`acc-mule-881\` and \`acc-intermediary-440\` share physical device fingerprint \`device-uuid-9918\`.
   - \`device-uuid-9918\` routed sessions through anonymous endpoint \`network-tor-exit-12\`.

#### Verified Evidence & Grounded Facts:
- All transaction records and timestamps verified from transaction logs.
- Sybil hardware clustering confirmed via distinct network relationship paths.
- **Recommended Action**: Freeze accounts \`acc-mule-881\` and \`acc-intermediary-440\` pending AML SAR filing.`,
    evidence_summary: {
      total_entities_verified: 5,
      unique_entities_count: 5,
      total_edges_inspected: 6,
      total_relationships_count: 6,
      total_paths_established: 2,
      duplicate_records_detected: 0,
      provenance_verification_rate: 1.0,
      entities: {
        "acc-mule-881": {
          id: "acc-mule-881",
          name: "Mule Account #881",
          kind: "Account",
          status: "flagged",
          properties: { balance_usd: 1240.0, risk_score: 0.94, jurisdiction: "KY" },
        },
        "acc-intermediary-440": {
          id: "acc-intermediary-440",
          name: "Intermediary Account #440",
          kind: "Account",
          status: "active",
          properties: { balance_usd: 600.0, risk_score: 0.82, jurisdiction: "PA" },
        },
        "acc-target-902": {
          id: "acc-target-902",
          name: "Beneficiary Wallet #902",
          kind: "Account",
          status: "watch_list",
          properties: { balance_usd: 95200.0, risk_score: 0.88, jurisdiction: "CH" },
        },
        "device-uuid-9918": {
          id: "device-uuid-9918",
          name: "Hardware Device UUID-9918",
          kind: "Device",
          status: "compromised",
          properties: { os: "Linux x86_64", browser: "Headless Chrome", first_seen: "2026-09-12" },
        },
        "network-tor-exit-12": {
          id: "network-tor-exit-12",
          name: "Tor Exit Node #12",
          kind: "Network",
          status: "anonymized",
          properties: { ip: "185.220.101.5", asn: "AS200052" },
        },
      },
      key_paths: [
        {
          source_id: "acc-mule-881",
          target_id: "acc-target-902",
          hop_count: 2,
          chain_names: ["Mule Account #881", "Intermediary Account #440", "Beneficiary Wallet #902"],
          relationships: ["TRANSFERS_TO", "TRANSFERS_TO"],
          is_verified: true,
        },
        {
          source_id: "acc-mule-881",
          target_id: "network-tor-exit-12",
          hop_count: 2,
          chain_names: ["Mule Account #881", "Hardware Device UUID-9918", "Tor Exit Node #12"],
          relationships: ["OWNS", "CONNECTS_TO"],
          is_verified: true,
        },
      ],
      unresolved_gaps: [],
    },
    steps: [
      {
        iteration: 1,
        thought: "Searching graph for anomalous transaction velocity starting at acc-mule-881.",
        tool_calls: [{ id: "c1", function_name: "search_connected_entities", arguments: { query: "acc-mule-881" } }],
        duration_seconds: 0.42,
      },
      {
        iteration: 2,
        thought: "Tracing multi-hop transfer relationships and shared hardware identifiers.",
        tool_calls: [{ id: "c2", function_name: "traverse_relationships", arguments: { entity_id: "acc-mule-881", depth: 3 } }],
        duration_seconds: 0.65,
      },
    ],
    total_iterations: 2,
    total_tool_calls: 2,
    duration_seconds: 1.48,
  },
  security: {
    objective: "Investigate these security findings, trace their connected dependencies, and identify which findings warrant attention.",
    success: true,
    final_answer: `### Executive Summary: Critical Attack Path to Production Database

Investigation of Security Finding **\`cve-2026-4412\`** reveals a verified privilege escalation path that directly reaches the primary customer credentials database:

1. **Vulnerability Assessment**:
   - \`cve-2026-4412\` (*CVSS 9.8 Critical: Remote Code Execution*) affects public gateway \`svc-auth-core\`.
2. **Identity Privilege Escalation**:
   - \`svc-auth-core\` is bound to IAM role \`role-auth-service-admin\`, which possesses excessive wildcard permissions \`iam:*\` and \`rds:*\`.
3. **Database Exposure**:
   - IAM role allows unauthenticated read replication of \`db-user-credentials-primary\` located in \`region-eu-central-1\`.

#### Verified Blast Radius:
- **3 Downstream Microservices**: \`svc-billing-api\`, \`svc-order-processing\`, \`svc-notification-core\`.
- **Primary Data Store**: 1.2M hashed user credentials exposed to potential exfiltration.
- **Recommended Action**: Rotate IAM role session credentials and immediately revoke wildcard database access for \`role-auth-service-admin\`.`,
    evidence_summary: {
      total_entities_verified: 5,
      unique_entities_count: 5,
      total_edges_inspected: 5,
      total_relationships_count: 5,
      total_paths_established: 1,
      duplicate_records_detected: 0,
      provenance_verification_rate: 1.0,
      entities: {
        "cve-2026-4412": {
          id: "cve-2026-4412",
          name: "CVE-2026-4412 (Critical RCE)",
          kind: "SecurityVulnerability",
          status: "critical",
          properties: { cvss: 9.8, cwe: "CWE-94", vector: "Network" },
        },
        "svc-auth-core": {
          id: "svc-auth-core",
          name: "Authentication Gateway Service",
          kind: "Service",
          status: "vulnerable",
          properties: { runtime: "Node 20", public_ingress: true, tier: "Tier-1" },
        },
        "role-auth-service-admin": {
          id: "role-auth-service-admin",
          name: "IAM Role: Auth Gateway Admin",
          kind: "IAMRole",
          status: "overprivileged",
          properties: { policy_arns: ["arn:aws:iam::aws:policy/AdministratorAccess"] },
        },
        "db-user-credentials-primary": {
          id: "db-user-credentials-primary",
          name: "User Credentials Primary DB",
          kind: "DatabaseInstance",
          status: "active",
          properties: { engine: "PostgreSQL 16", multi_az: true, records_count: 1240000 },
        },
        "region-eu-central-1": {
          id: "region-eu-central-1",
          name: "Frankfurt Region (eu-central-1)",
          kind: "CloudRegion",
          status: "healthy",
          properties: { provider: "AWS", compliance: "GDPR-Tier1" },
        },
      },
      key_paths: [
        {
          source_id: "cve-2026-4412",
          target_id: "db-user-credentials-primary",
          hop_count: 3,
          chain_names: [
            "CVE-2026-4412 (Critical RCE)",
            "Authentication Gateway Service",
            "IAM Role: Auth Gateway Admin",
            "User Credentials Primary DB",
          ],
          relationships: ["AFFECTS", "ASSUMES_ROLE", "ACCESSES"],
          is_verified: true,
        },
      ],
      unresolved_gaps: [],
    },
    steps: [
      {
        iteration: 1,
        thought: "Querying security finding cve-2026-4412 and inspecting host services.",
        tool_calls: [{ id: "c1", function_name: "get_entity_profile", arguments: { entity_id: "cve-2026-4412" } }],
        duration_seconds: 0.38,
      },
      {
        iteration: 2,
        thought: "Evaluating blast radius from svc-auth-core into cloud IAM and data stores.",
        tool_calls: [{ id: "c2", function_name: "inspect_entity_neighbors", arguments: { entity_id: "svc-auth-core", direction: "outgoing" } }],
        duration_seconds: 0.54,
      },
    ],
    total_iterations: 2,
    total_tool_calls: 2,
    duration_seconds: 1.25,
  },
  codebase: {
    objective: "Trace dependencies related to this component and identify the possible impact of a proposed change.",
    success: true,
    final_answer: `### Executive Summary: Release Bottleneck Resolved via Policy Reassignment

Multi-hop dependency analysis of release **\`release-payments-2026-10\`** pinpoints an unresolved review bottleneck on Pull Request **\`#482\`**:

1. **Release Dependency Chain**:
   - \`release-payments-2026-10\` (*delayed*) deploys \`service-payment-api\`.
   - \`service-payment-api\` is implemented in repository \`repo-payment-api\`, which has pending pull request \`pr-482\`.
2. **Review Task Blockage**:
   - \`pr-482\` is blocked by review task \`task-code-review-482\` (status: \`in_progress\`).
   - Assigned engineer \`person-liam-patel\` is currently \`on_leave\` with active leave event \`event-liam-leave\`.
3. **Governance Unblocking**:
   - Policy check against \`policy-code-review-reassignment\` verifies that reassigning to available Staff Engineer **Ravi Kulkarni** (\`person-ravi-kulkarni\`) unblocks the path without compliance violations.

#### Verified Evidence:
- Complete 5-hop path verified across Git and HR records with 1.0 confidence.
- **Recommended Action**: Approve reassignment of \`task-code-review-482\` to Ravi Kulkarni.`,
    evidence_summary: {
      total_entities_verified: 6,
      unique_entities_count: 6,
      total_edges_inspected: 6,
      total_relationships_count: 6,
      total_paths_established: 1,
      duplicate_records_detected: 0,
      provenance_verification_rate: 1.0,
      entities: {
        "release-payments-2026-10": {
          id: "release-payments-2026-10",
          name: "Payments Release October 2026",
          kind: "Release",
          status: "delayed",
          properties: { target_date: "2026-10-20", tier: "Production" },
        },
        "service-payment-api": {
          id: "service-payment-api",
          name: "Payment API Service",
          kind: "Service",
          status: "active",
          properties: { tier: "Tier-1", language: "TypeScript" },
        },
        "repo-payment-api": {
          id: "repo-payment-api",
          name: "payment-api repository",
          kind: "Repository",
          status: "active",
          properties: { default_branch: "main", visibility: "internal" },
        },
        "pr-482": {
          id: "pr-482",
          name: "PR #482: Update payments SDK",
          kind: "PullRequest",
          status: "awaiting_review",
          properties: { author: "Sarah Chen", lines_changed: 340 },
        },
        "task-code-review-482": {
          id: "task-code-review-482",
          name: "Code Review #482",
          kind: "Task",
          status: "in_progress",
          properties: { priority: "P0", due_date: "2026-10-16" },
        },
        "person-liam-patel": {
          id: "person-liam-patel",
          name: "Liam Patel",
          kind: "Person",
          status: "on_leave",
          properties: { role: "Senior Engineer", availability: "on_leave" },
        },
      },
      key_paths: [
        {
          source_id: "release-payments-2026-10",
          target_id: "person-liam-patel",
          hop_count: 5,
          chain_names: [
            "Payments Release October 2026",
            "Payment API Service",
            "payment-api repository",
            "PR #482: Update payments SDK",
            "Code Review #482",
            "Liam Patel",
          ],
          relationships: ["DEPLOYS", "IMPLEMENTED_IN", "HAS_PULL_REQUEST", "BLOCKED_BY", "ASSIGNED_TO"],
          is_verified: true,
        },
      ],
      unresolved_gaps: [],
    },
    steps: [
      {
        iteration: 1,
        thought: "Searching for delayed release entity release-payments-2026-10.",
        tool_calls: [{ id: "c1", function_name: "get_entity_profile", arguments: { entity_id: "release-payments-2026-10" } }],
        duration_seconds: 0.35,
      },
      {
        iteration: 2,
        thought: "Traversing relationships downstream through pull requests and blocking tasks.",
        tool_calls: [{ id: "c2", function_name: "traverse_relationships", arguments: { entity_id: "release-payments-2026-10", depth: 4 } }],
        duration_seconds: 0.72,
      },
    ],
    total_iterations: 2,
    total_tool_calls: 2,
    duration_seconds: 1.35,
  },
};
