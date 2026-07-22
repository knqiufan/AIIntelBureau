export type AgentId = "detective" | "informant" | "suspect" | "bulletin_board";
export type Certainty = "known" | "unknown";

export interface MemoryCard {
  id: string;
  content: string;
  owner_agent_id: AgentId;
  visibility: "private" | "public";
  topic: string;
  kind: string;
  score?: number | null;
  source_agent_id?: AgentId | null;
  source_memory_id?: string | null;
  created_at: string;
}

export interface RetrievalTrace {
  request_id: string;
  query: string;
  searched_scopes: AgentId[];
  hit_cards: MemoryCard[];
  duration_ms: number;
  mode: "full" | "degrade";
}

export interface AnswerView {
  answer: string;
  certainty: Certainty;
  evidence_ids: string[];
  trace: RetrievalTrace;
  responder: "deterministic" | "deepagents";
  fallback_reason?: string | null;
}

export interface CaseState {
  case_id: string;
  script_id?: "password" | "mole" | "allergy" | null;
  version: number;
  status: "empty" | "ready";
  created_at: string;
}

export interface Snapshot {
  case: CaseState;
  spaces: Record<AgentId, MemoryCard[]>;
  last_trace?: RetrievalTrace | null;
  last_answer?: AnswerView | null;
}

export interface PublicMemoryCard {
  id: string;
  content: string;
  topic: string;
  kind: string;
  source_agent_id: Exclude<AgentId, "bulletin_board">;
  created_at: string;
}

export interface StageRetrieval {
  searched_scopes: AgentId[];
  public_hit_cards: PublicMemoryCard[];
  duration_ms: number;
}

export interface StageSnapshot {
  case: CaseState;
  private_memory_counts: Record<Exclude<AgentId, "bulletin_board">, number>;
  bulletin_board: PublicMemoryCard[];
  last_retrieval?: StageRetrieval | null;
}

export interface HealthPart {
  status: "ok" | "degraded" | "unconfigured" | "error";
  detail: string;
}

export interface Health {
  api: HealthPart;
  powermem: HealthPart;
  seekdb: HealthPart;
  llm: HealthPart;
  mode: "full" | "degrade";
}

export interface AdvancedFeatures {
  enabled: boolean;
  audit_timeline_enabled: boolean;
  board_analysis_enabled: boolean;
  unsafe_fixture_enabled: boolean;
  native_share_experiment_enabled: boolean;
  freeform_whisper_enabled: boolean;
  native_share_note: string;
}

export interface AuditEntry {
  event_id: number;
  created_at: string;
  operator: string;
  source_agent_id: AgentId;
  source_memory_id: string;
  public_card_id: string;
}

export interface AuditTimeline {
  case_id: string;
  entries: AuditEntry[];
}

export interface PublicFact {
  card_id: string;
  statement: string;
  topic: string;
  source_agent_id: AgentId;
}

export interface AnalysisRisk {
  severity: "low" | "medium" | "high";
  title: string;
  detail: string;
  related_card_ids: string[];
}

export interface BoardAnalysis {
  query: string;
  facts: PublicFact[];
  risks: AnalysisRisk[];
  responder: "deterministic" | "deepagents";
  notice: string;
}

export interface UnsafeFixture {
  fixture_id: string;
  case_id: string;
  tool_name: "unsafe_global_search";
  warning: string;
  result_count: number;
}
