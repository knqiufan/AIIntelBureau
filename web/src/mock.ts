import p1Password from "./fixtures/p1-password.json";
import type { ApiClient, EventListener, EventStatusListener } from "./api";
import type { AdvancedFeatures, AgentId, AnswerView, AuditTimeline, BoardAnalysis, Health, MemoryCard, PublicMemoryCard, Snapshot, StageSnapshot, UnsafeFixture } from "./types";
import type { GameEvent } from "./lib/guide";

type ScriptId = "password" | "mole" | "allergy";
type StorageLike = Pick<Storage, "getItem" | "setItem">;

type MockState = {
  cases: Record<string, Snapshot>;
  events: Record<string, GameEvent[]>;
  serial: number;
};

const STORAGE_KEY = "ai-intel-bureau.mock-state.v1";
const roleIds: AgentId[] = ["detective", "informant", "suspect", "bulletin_board"];

const fallbackSeeds: Record<Exclude<ScriptId, "password">, Omit<MemoryCard, "created_at" | "visibility">[]> = {
  mole: [
    { id: "p1-informant-mole", content: "真情报：内鬼今晚在码头接头，暗号是蓝雨伞。", owner_agent_id: "informant", topic: "mole", kind: "evidence" },
    { id: "p1-detective-mole", content: "我只相信公告板上的情报开展行动。", owner_agent_id: "detective", topic: "mole", kind: "evidence" },
    { id: "p1-suspect-mole", content: "我不是内鬼，但我听说码头最近风声紧。", owner_agent_id: "suspect", topic: "mole", kind: "alibi" },
  ],
  allergy: [
    { id: "p1-detective-allergy", content: "虚构用户对花生严重过敏。", owner_agent_id: "detective", topic: "allergy", kind: "secret" },
    { id: "p1-informant-allergy", content: "虚构用户昨天说想吃泰餐。", owner_agent_id: "informant", topic: "dining", kind: "evidence" },
    { id: "p1-suspect-allergy", content: "虚构用户喜欢晚上 9 点运动。", owner_agent_id: "suspect", topic: "routine", kind: "evidence" },
  ],
};

function clone<T>(value: T): T {
  return structuredClone(value);
}

function emptySpaces(): Snapshot["spaces"] {
  return { detective: [], informant: [], suspect: [], bulletin_board: [] };
}

function memoryStorage(): StorageLike | undefined {
  if (typeof sessionStorage === "undefined") return undefined;
  return sessionStorage;
}

function restore(storage: StorageLike | undefined): MockState {
  if (!storage) return { cases: {}, events: {}, serial: 0 };
  try {
    const stored = storage.getItem(STORAGE_KEY);
    if (stored) return JSON.parse(stored) as MockState;
  } catch { /* A corrupt mock cache should never block the UI. */ }
  return { cases: {}, events: {}, serial: 0 };
}

function scriptCards(scriptId: ScriptId): MemoryCard[] {
  const createdAt = new Date().toISOString();
  if (scriptId === "password") {
    return p1Password.cards.map((card) => ({ ...card, created_at: createdAt }) as MemoryCard);
  }
  return fallbackSeeds[scriptId].map((card) => ({ ...card, visibility: "private", created_at: createdAt }));
}

function questionMatches(card: MemoryCard, question: string): boolean {
  const normalized = question.toLowerCase();
  if (/密码|保险箱|0427/.test(question)) return card.topic === "password" || card.content.includes("0427");
  if (/掌握|情报|知道/.test(question)) return true;
  return [card.content.toLowerCase(), card.topic.toLowerCase(), card.kind.toLowerCase()].some((value) => value.includes(normalized));
}

export function createMockApi(eventDelayMs = 0, storage = memoryStorage()): ApiClient {
  const state = restore(storage);
  const listeners = new Map<string, Set<EventListener>>();

  const persist = () => storage?.setItem(STORAGE_KEY, JSON.stringify(state));
  const snapshotFor = (caseId: string): Snapshot => {
    const snapshot = state.cases[caseId];
    if (!snapshot) throw new Error("Mock 案件不存在，请新开案件后重试。");
    return snapshot;
  };
  const save = (caseId: string, snapshot: Snapshot) => {
    state.cases[caseId] = snapshot;
    persist();
    return clone(snapshot);
  };
  const stageSnapshotFor = (caseId: string): StageSnapshot => {
    const snapshot = snapshotFor(caseId);
    const publicCard = (card: MemoryCard): PublicMemoryCard => ({
      id: card.id,
      content: card.content,
      topic: card.topic,
      kind: card.kind,
      source_agent_id: card.source_agent_id! as PublicMemoryCard["source_agent_id"],
      created_at: card.created_at,
    });
    return {
      case: clone(snapshot.case),
      private_memory_counts: {
        detective: snapshot.spaces.detective.length,
        informant: snapshot.spaces.informant.length,
        suspect: snapshot.spaces.suspect.length,
      },
      bulletin_board: snapshot.spaces.bulletin_board.map(publicCard),
      last_retrieval: snapshot.last_trace ? {
        searched_scopes: clone(snapshot.last_trace.searched_scopes),
        public_hit_cards: snapshot.last_trace.hit_cards.filter((card) => card.visibility === "public").map(publicCard),
        duration_ms: snapshot.last_trace.duration_ms,
      } : null,
    };
  };
  const requestId = () => `mock_req_${++state.serial}`;
  const emit = (caseId: string, type: string, payload: Record<string, unknown>, id = requestId()) => {
    const event: GameEvent = { type, request_id: id, payload };
    (state.events[caseId] ??= []).push(event);
    persist();
    setTimeout(() => listeners.get(caseId)?.forEach((listener) => listener(clone(event))), eventDelayMs);
    return id;
  };
  const requireVersion = (snapshot: Snapshot, expectedVersion: number) => {
    if (snapshot.case.version !== expectedVersion) throw new Error("案件版本已变化；请等待同步后重试。");
  };

  const health: Health = {
    api: { status: "ok", detail: "Mock API is serving the UI fixture" },
    powermem: { status: "ok", detail: "P1 JSON fixture is active" },
    seekdb: { status: "ok", detail: "Mock event source is active" },
    llm: { status: "degraded", detail: "Mock mode uses deterministic evidence answers" },
    mode: "degrade",
  };
  const advanced: AdvancedFeatures = {
    enabled: true,
    audit_timeline_enabled: true,
    board_analysis_enabled: true,
    // Keep the same P4 safety invariant as the API: this fixture cannot run
    // alongside audience freeform input.
    unsafe_fixture_enabled: false,
    native_share_experiment_enabled: false,
    freeform_whisper_enabled: true,
    native_share_note: "Mock 仅展示契约状态；主演示仍使用公告板复制。",
  };

  return {
    isMock: true,
    setActivityKey: () => undefined,
    establishActivitySession: async () => undefined,
    createCase: async () => {
      const caseId = `mock-${++state.serial}`;
      const snapshot: Snapshot = {
        case: { case_id: caseId, version: 0, status: "empty", script_id: null, created_at: new Date().toISOString() },
        spaces: emptySpaces(), last_trace: null, last_answer: null,
      };
      save(caseId, snapshot);
      emit(caseId, "case.created", { version: 0, status: "empty" });
      return clone(snapshot);
    },
    snapshot: async (caseId) => clone(snapshotFor(caseId)),
    stageSnapshot: async (caseId) => clone(stageSnapshotFor(caseId)),
    health: async () => clone(health),
    advancedStatus: async () => clone(advanced),
    loadScript: async (caseId, scriptId, expectedVersion) => {
      const current = clone(snapshotFor(caseId));
      requireVersion(current, expectedVersion);
      if (current.case.script_id === scriptId) return current;
      const cards = scriptCards(scriptId);
      cards.forEach((card) => current.spaces[card.owner_agent_id].push(card));
      current.case = { ...current.case, script_id: scriptId, status: "ready", version: current.case.version + 1 };
      current.last_trace = null; current.last_answer = null;
      save(caseId, current);
      const id = requestId();
      cards.forEach((card) => emit(caseId, "memory.created", { card_id: card.id, owner_agent_id: card.owner_agent_id, visibility: "private", topic: card.topic, kind: card.kind }, id));
      emit(caseId, "script.loaded", { script_id: scriptId, version: current.case.version, card_ids: cards.map((card) => card.id) }, id);
      return clone(current);
    },
    resetCase: async (caseId, expectedVersion) => {
      const current = clone(snapshotFor(caseId));
      requireVersion(current, expectedVersion);
      const reset: Snapshot = { ...current, case: { ...current.case, script_id: null, status: "empty", version: current.case.version + 1 }, spaces: emptySpaces(), last_trace: null, last_answer: null };
      save(caseId, reset);
      emit(caseId, "case.reset", { version: reset.case.version, status: "empty" });
      return clone(reset);
    },
    whisper: async (caseId, agentId, text, expectedVersion) => {
      const current = clone(snapshotFor(caseId));
      requireVersion(current, expectedVersion);
      if (agentId === "bulletin_board") throw new Error("公告板不能接收私有耳语。");
      const card: MemoryCard = { id: `mock_whisper_${++state.serial}`, content: text, owner_agent_id: agentId, visibility: "private", topic: "operator_whisper", kind: "evidence", created_at: new Date().toISOString() };
      current.spaces[agentId].push(card);
      current.case = { ...current.case, version: current.case.version + 1 };
      save(caseId, current);
      emit(caseId, "memory.created", { card_id: card.id, owner_agent_id: agentId, visibility: "private", topic: card.topic, kind: card.kind });
      return { snapshot: clone(current) };
    },
    interrogate: async (caseId, agentId, question, expectedVersion) => {
      const current = clone(snapshotFor(caseId));
      requireVersion(current, expectedVersion);
      if (agentId === "bulletin_board") throw new Error("公告板不是可审问角色。");
      const cards = [...current.spaces[agentId], ...current.spaces.bulletin_board].filter((card) => questionMatches(card, question));
      const id = requestId();
      const trace = { request_id: id, query: question, searched_scopes: [agentId, "bulletin_board"] as AgentId[], hit_cards: cards, duration_ms: eventDelayMs, mode: "degrade" as const };
      const answer: AnswerView = cards.length
        ? { answer: `根据当前可见情报：${cards[0].content}`, certainty: "known", evidence_ids: [cards[0].id], responder: "deterministic", trace, fallback_reason: null }
        : { answer: "我不知道；当前可见记忆中没有这方面的情报。", certainty: "unknown", evidence_ids: [], responder: "deterministic", trace, fallback_reason: null };
      current.last_trace = trace; current.last_answer = answer;
      save(caseId, current);
      emit(caseId, "retrieval.completed", { agent_id: agentId, searched_scopes: trace.searched_scopes, hit_card_ids: cards.map((card) => card.id), duration_ms: trace.duration_ms, mode: trace.mode }, id);
      emit(caseId, "answer.completed", { certainty: answer.certainty, evidence_ids: answer.evidence_ids, responder: answer.responder, fallback_reason: null, trace_id: id }, id);
      return clone(answer);
    },
    publish: async (caseId, agentId, memoryId, expectedVersion) => {
      const current = clone(snapshotFor(caseId));
      requireVersion(current, expectedVersion);
      const source = current.spaces[agentId].find((card) => card.id === memoryId);
      if (!source || source.visibility !== "private") throw new Error("所选记忆不属于当前案件和角色。");
      const existing = current.spaces.bulletin_board.find((card) => card.source_memory_id === source.id);
      if (existing) return { snapshot: current };
      const id = requestId();
      const publicCard: MemoryCard = { ...source, id: `mock_public_${source.id}`, owner_agent_id: "bulletin_board", visibility: "public", source_agent_id: agentId, source_memory_id: source.id, created_at: new Date().toISOString() };
      current.spaces.bulletin_board.push(publicCard);
      current.case = { ...current.case, version: current.case.version + 1 };
      save(caseId, current);
      emit(caseId, "memory.publishing", { source_memory_id: source.id, source_agent_id: agentId }, id);
      emit(caseId, "memory.published", { source_memory_id: source.id, source_agent_id: agentId, public_card: { card_id: publicCard.id, owner_agent_id: "bulletin_board", visibility: "public", source_agent_id: agentId, source_memory_id: source.id }, version: current.case.version }, id);
      return { snapshot: clone(current) };
    },
    auditTimeline: async (caseId): Promise<AuditTimeline> => {
      snapshotFor(caseId);
      const entries = (state.events[caseId] ?? []).flatMap((event, index) => {
        if (event.type !== "memory.published") return [];
        const sourceAgent = event.payload.source_agent_id;
        const sourceMemory = event.payload.source_memory_id;
        const publicCard = event.payload.public_card as { card_id?: string } | undefined;
        if (typeof sourceAgent !== "string" || typeof sourceMemory !== "string" || !publicCard?.card_id) return [];
        return [{ event_id: index + 1, created_at: new Date().toISOString(), operator: "局长", source_agent_id: sourceAgent as AgentId, source_memory_id: sourceMemory, public_card_id: publicCard.card_id }];
      });
      return { case_id: caseId, entries };
    },
    analyzeBoard: async (caseId, query): Promise<BoardAnalysis> => {
      const snapshot = snapshotFor(caseId);
      const cards = snapshot.spaces.bulletin_board.filter((card) => questionMatches(card, query));
      return {
        query,
        facts: cards.map((card) => ({ card_id: card.id, statement: card.content, topic: card.topic, source_agent_id: card.source_agent_id ?? "bulletin_board" })),
        risks: cards.length ? [] : [{ severity: "low", title: "没有命中公开材料", detail: "Mock 分析器没有读取私有空间；先公开材料或调整问题。", related_card_ids: [] }],
        responder: "deterministic",
        notice: "辅助分析，不改变角色可见记忆。",
      };
    },
    startUnsafeFixture: async (): Promise<UnsafeFixture> => {
      throw new Error("Mock 已启用自由耳语，因此隔离反面教材 fixture 不可用。");
    },
    closeUnsafeFixture: async () => undefined,
    eventUrl: (caseId, afterId = 0) => `mock://cases/${caseId}/events?after_event_id=${afterId}`,
    subscribeEvents: (caseId, onEvent, onStatus) => {
      onStatus("open");
      const bucket = listeners.get(caseId) ?? new Set<EventListener>();
      bucket.add(onEvent); listeners.set(caseId, bucket);
      const timers = (state.events[caseId] ?? []).map((event, index) => setTimeout(() => onEvent(clone(event)), eventDelayMs * (index + 1)));
      return () => {
        timers.forEach((timer) => clearTimeout(timer));
        bucket.delete(onEvent);
        if (bucket.size === 0) listeners.delete(caseId);
      };
    },
    subscribeStageEvents: (caseId, onEvent, onStatus) => {
      onStatus("open");
      const bucket = listeners.get(caseId) ?? new Set<EventListener>();
      bucket.add(onEvent); listeners.set(caseId, bucket);
      const timers = (state.events[caseId] ?? []).map((event, index) => setTimeout(() => onEvent(clone(event)), eventDelayMs * (index + 1)));
      return () => {
        timers.forEach((timer) => clearTimeout(timer));
        bucket.delete(onEvent);
        if (bucket.size === 0) listeners.delete(caseId);
      };
    },
  };
}
