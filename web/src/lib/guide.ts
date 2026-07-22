import type { AgentId, AnswerView, Snapshot } from "../types";

export type GuideState = {
  scriptLoaded: boolean;
  detectiveMissed: boolean;
  informantKnown: boolean;
  published: boolean;
  detectiveKnownAfterPublish: boolean;
  pendingScopes: Record<string, AgentId>;
};

export type GameEvent = {
  type: string;
  request_id: string;
  payload: Record<string, unknown>;
};

export const emptyGuideState = (): GuideState => ({
  scriptLoaded: false,
  detectiveMissed: false,
  informantKnown: false,
  published: false,
  detectiveKnownAfterPublish: false,
  pendingScopes: {},
});

export function recordScriptLoaded(state: GuideState): GuideState {
  return { ...state, scriptLoaded: true };
}

export function recordPublication(state: GuideState): GuideState {
  return { ...state, published: true };
}

export function recordInterrogation(state: GuideState, agentId: AgentId, answer: AnswerView): GuideState {
  if (agentId === "detective" && answer.certainty === "unknown") {
    return { ...state, detectiveMissed: true };
  }
  if (agentId === "informant" && answer.certainty === "known") {
    return { ...state, informantKnown: true };
  }
  if (agentId === "detective" && answer.certainty === "known" && state.published) {
    return { ...state, detectiveKnownAfterPublish: true };
  }
  return state;
}

/** Derive guide state from authoritative event replay; it stores no game facts. */
export function applyGuideEvent(state: GuideState, event: GameEvent): GuideState {
  if (event.type === "case.reset") return emptyGuideState();
  if (event.type === "script.loaded") return recordScriptLoaded(state);
  if (event.type === "memory.published") return recordPublication(state);
  if (event.type === "retrieval.completed") {
    const agentId = event.payload.agent_id;
    if (agentId === "detective" || agentId === "informant" || agentId === "suspect") {
      return { ...state, pendingScopes: { ...state.pendingScopes, [event.request_id]: agentId } };
    }
    return state;
  }
  if (event.type === "answer.completed") {
    const agentId = state.pendingScopes[event.request_id];
    const certainty = event.payload.certainty;
    const withoutPending = { ...state, pendingScopes: Object.fromEntries(Object.entries(state.pendingScopes).filter(([requestId]) => requestId !== event.request_id)) };
    if (!agentId || (certainty !== "known" && certainty !== "unknown")) return withoutPending;
    return recordInterrogation(withoutPending, agentId, {
      answer: "",
      certainty,
      evidence_ids: [],
      responder: "deterministic",
      trace: { request_id: event.request_id, query: "", searched_scopes: [agentId, "bulletin_board"], hit_cards: [], duration_ms: 0, mode: "degrade" },
    });
  }
  return state;
}

export function guideCompletion(snapshot: Snapshot, guide: GuideState): boolean[] {
  return [
    guide.scriptLoaded || Boolean(snapshot.case.script_id),
    guide.detectiveMissed,
    guide.informantKnown && guide.published,
    guide.detectiveKnownAfterPublish,
  ];
}
