export interface EntityFact {
  id: string;
  name?: string;
  kind?: string;
  status?: string;
  source_ref?: string;
  properties?: Record<string, any>;
  is_isolated?: boolean;
  relationship_contract?: string;
  labels?: string[];
}

export interface RelationshipEdge {
  from_id: string;
  relationship_type: string;
  to_id: string;
  source_record_id?: string;
  observed_at?: string;
  confidence?: number;
  properties?: Record<string, any>;
}

export interface EvidencePath {
  source_id: string;
  target_id: string;
  hop_count: number;
  chain_names: string[];
  relationships: string[];
  is_verified: boolean;
}

export interface EvidenceSummary {
  total_entities_verified: number;
  unique_entities_count: number;
  total_edges_inspected: number;
  total_relationships_count: number;
  total_paths_established: number;
  duplicate_records_detected: number;
  provenance_verification_rate: number;
  entities: Record<string, EntityFact>;
  key_paths: EvidencePath[];
  unresolved_gaps: string[];
}

export interface ToolCallItem {
  id: string;
  function_name: string;
  arguments: Record<string, any>;
}

export interface AgentStepItem {
  iteration: number;
  thought?: string;
  tool_calls: ToolCallItem[];
  tool_results?: any[];
  duration_seconds: number;
}

export interface InvestigationEvent {
  type: "plan" | "thought" | "tool_call" | "tool_result" | "limit_reached" | "guardrail_blocked" | "complete" | "error";
  iteration: number;
  message: string;
  metadata?: Record<string, any>;
  timestamp?: string;
}

export interface InvestigationResult {
  objective: string;
  success: boolean;
  final_answer: string;
  evidence_summary: EvidenceSummary;
  steps: AgentStepItem[];
  total_iterations: number;
  total_tool_calls: number;
  duration_seconds: number;
  provider_info?: Record<string, any>;
  unresolved_questions?: string[];
}

export interface GraphSchemaProfile {
  tenant_graph: string;
  inferred_domain: string;
  total_nodes: number;
  total_edges: number;
  graph_density?: number;
  average_degree?: number;
  node_kinds: Array<{ kind: string; count?: number } | string>;
  relationship_types: Array<{ type: string; total_instances?: number } | string>;
  property_catalog?: Record<string, any>;
}

export interface HealthStatus {
  status: string;
  service: string;
  provider: string;
  model: string;
  graph_name: string;
  mcp_transport: string;
  read_only: boolean;
  max_iterations: number;
  max_tool_calls: number;
}
