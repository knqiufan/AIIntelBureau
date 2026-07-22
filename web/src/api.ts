import { createMockApi } from "./mock";
import type { GameEvent } from "./lib/guide";
import type { AdvancedFeatures, AgentId, AnswerView, AuditTimeline, BoardAnalysis, Health, Snapshot, StageSnapshot, UnsafeFixture } from "./types";

export type EventStatus = "open" | "error";
export type EventListener = (event: GameEvent) => void;
export type EventStatusListener = (status: EventStatus) => void;

export class ApiError extends Error {
  constructor(readonly status: number, readonly code: string | undefined, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export interface ApiClient {
  readonly isMock: boolean;
  setActivityKey: (key: string) => void;
  establishActivitySession: () => Promise<void>;
  createCase: () => Promise<Snapshot>;
  snapshot: (caseId: string) => Promise<Snapshot>;
  stageSnapshot: (caseId: string) => Promise<StageSnapshot>;
  health: () => Promise<Health>;
  advancedStatus: () => Promise<AdvancedFeatures>;
  loadScript: (caseId: string, scriptId: "password" | "mole" | "allergy", expectedVersion: number) => Promise<Snapshot>;
  resetCase: (caseId: string, expectedVersion: number) => Promise<Snapshot>;
  whisper: (caseId: string, agentId: AgentId, text: string, expectedVersion: number) => Promise<{ snapshot: Snapshot }>;
  interrogate: (caseId: string, agentId: AgentId, question: string, expectedVersion: number) => Promise<AnswerView>;
  publish: (caseId: string, agentId: AgentId, memoryId: string, expectedVersion: number) => Promise<{ snapshot: Snapshot }>;
  auditTimeline: (caseId: string) => Promise<AuditTimeline>;
  analyzeBoard: (caseId: string, query: string) => Promise<BoardAnalysis>;
  startUnsafeFixture: () => Promise<UnsafeFixture>;
  closeUnsafeFixture: (fixtureId: string) => Promise<void>;
  eventUrl: (caseId: string, afterId?: number) => string;
  subscribeEvents: (caseId: string, onEvent: EventListener, onStatus: EventStatusListener) => () => void;
  subscribeStageEvents: (caseId: string, onEvent: EventListener, onStatus: EventStatusListener) => () => void;
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
let activityKey = "";
let csrfTokenValue = "";

function endpoint(path: string): string {
  return `${API_BASE}${path}`;
}

function csrfToken(): string {
  if (csrfTokenValue) return csrfTokenValue;
  const name = window.location.pathname.startsWith("/stage/") ? "ai_intel_bureau_stage_csrf" : "ai_intel_bureau_operator_csrf";
  const entry = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith(`${name}=`));
  return entry ? decodeURIComponent(entry.slice(name.length + 1)) : "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(endpoint(path), {
    ...init,
    credentials: init?.credentials ?? "include",
    headers: {
      "Content-Type": "application/json",
      ...(activityKey ? { "X-Demo-Access-Key": activityKey } : {}),
      ...(init?.method && init.method !== "GET" && init.method !== "HEAD" && csrfToken() ? { "X-CSRF-Token": csrfToken() } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new ApiError(response.status, payload?.detail?.code, payload?.detail?.message ?? "操作未完成，请重试。");
  }
  if (path === "/api/session") csrfTokenValue = response.headers.get("X-CSRF-Token") ?? "";
  return response.status === 204 ? undefined as T : response.json() as Promise<T>;
}

const eventTypes = ["case.created", "case.reset", "script.loaded", "memory.created", "retrieval.completed", "answer.completed", "agent.fallback", "memory.publishing", "memory.published"];

function cursorStorageKey(scope: "operator" | "stage", caseId: string): string {
  return `ai-intel-bureau:sse:${scope}:${caseId}`;
}

function storedCursor(scope: "operator" | "stage", caseId: string): number {
  const parsed = Number(sessionStorage.getItem(cursorStorageKey(scope, caseId)) ?? "0");
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : 0;
}

function rememberCursor(scope: "operator" | "stage", caseId: string, event: Event): void {
  const value = Number((event as MessageEvent<string>).lastEventId);
  if (Number.isSafeInteger(value) && value > 0) sessionStorage.setItem(cursorStorageKey(scope, caseId), String(value));
}

const httpApi: ApiClient = {
  isMock: false,
  setActivityKey: (key) => {
    activityKey = key.trim();
  },
  establishActivitySession: async () => {
    try {
      await request<void>("/api/session", { method: "POST" });
    } finally {
      // Only the passcode exchange uses a header.  Subsequent API and SSE
      // traffic relies on the HttpOnly, role-scoped session cookie.
      activityKey = "";
    }
  },
  createCase: () => request<Snapshot>("/api/cases", { method: "POST" }),
  snapshot: (caseId: string) => request<Snapshot>(`/api/cases/${caseId}/operator-snapshot`),
  stageSnapshot: (caseId: string) => request<StageSnapshot>(`/api/cases/${caseId}/stage-snapshot`),
  health: () => request<Health>("/api/healthz"),
  advancedStatus: () => request<AdvancedFeatures>("/api/advanced/status"),
  loadScript: (caseId: string, scriptId: "password" | "mole" | "allergy", expectedVersion: number) =>
    request<Snapshot>(`/api/cases/${caseId}/script`, { method: "POST", body: JSON.stringify({ script_id: scriptId, expected_version: expectedVersion }) }),
  resetCase: (caseId: string, expectedVersion: number) =>
    request<Snapshot>(`/api/cases/${caseId}/reset`, { method: "POST", body: JSON.stringify({ expected_version: expectedVersion }) }),
  whisper: (caseId: string, agentId: AgentId, text: string, expectedVersion: number) =>
    request<{ snapshot: Snapshot }>(`/api/cases/${caseId}/whispers`, { method: "POST", body: JSON.stringify({ agent_id: agentId, text, expected_version: expectedVersion }) }),
  interrogate: (caseId: string, agentId: AgentId, question: string, expectedVersion: number) =>
    request<AnswerView>(`/api/cases/${caseId}/interrogations`, { method: "POST", body: JSON.stringify({ agent_id: agentId, question, expected_version: expectedVersion }) }),
  publish: (caseId: string, agentId: AgentId, memoryId: string, expectedVersion: number) =>
    request<{ snapshot: Snapshot }>(`/api/cases/${caseId}/publications`, { method: "POST", body: JSON.stringify({ source_agent_id: agentId, memory_id: memoryId, expected_version: expectedVersion }) }),
  auditTimeline: (caseId: string) => request<AuditTimeline>(`/api/cases/${caseId}/audit`),
  analyzeBoard: (caseId: string, query: string) => request<BoardAnalysis>(`/api/cases/${caseId}/board-analysis`, { method: "POST", body: JSON.stringify({ query }) }),
  startUnsafeFixture: () => request<UnsafeFixture>("/api/advanced/unsafe-fixture", { method: "POST" }),
  closeUnsafeFixture: (fixtureId: string) => request<void>(`/api/advanced/unsafe-fixture/${fixtureId}`, { method: "DELETE" }),
  eventUrl: (caseId: string, afterId = 0) => endpoint(`/api/cases/${caseId}/operator-events?after_event_id=${afterId}`),
  subscribeEvents: (caseId, onEvent, onStatus) => {
    const source = new EventSource(httpApi.eventUrl(caseId, storedCursor("operator", caseId)), { withCredentials: true });
    const update = (event: Event) => {
      rememberCursor("operator", caseId, event);
      try { onEvent(JSON.parse((event as MessageEvent<string>).data) as GameEvent); } catch { /* Snapshot refresh remains available. */ }
    };
    eventTypes.forEach((eventType) => source.addEventListener(eventType, update));
    source.onerror = () => onStatus("error");
    source.onopen = () => onStatus("open");
    return () => source.close();
  },
  subscribeStageEvents: (caseId, onEvent, onStatus) => {
    const source = new EventSource(endpoint(`/api/cases/${caseId}/stage-events?after_event_id=${storedCursor("stage", caseId)}`), { withCredentials: true });
    const update = (event: Event) => {
      rememberCursor("stage", caseId, event);
      try { onEvent(JSON.parse((event as MessageEvent<string>).data) as GameEvent); } catch { /* Snapshot refresh remains available. */ }
    };
    eventTypes.forEach((eventType) => source.addEventListener(eventType, update));
    source.onerror = () => onStatus("error");
    source.onopen = () => onStatus("open");
    return () => source.close();
  },
};

const mockDelay = Number(import.meta.env.VITE_MOCK_EVENT_DELAY_MS ?? "0");
export const api: ApiClient = import.meta.env.VITE_DEMO_DATA_SOURCE === "mock"
  ? createMockApi(Number.isFinite(mockDelay) ? Math.max(0, mockDelay) : 0)
  : httpApi;
