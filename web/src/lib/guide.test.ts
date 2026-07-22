import { describe, expect, it } from "vitest";
import { applyGuideEvent, emptyGuideState, guideCompletion, recordInterrogation, recordPublication, recordScriptLoaded } from "./guide";
import type { AnswerView, Snapshot } from "../types";

const base: Snapshot = {
  case: { case_id: "test", version: 1, status: "ready", script_id: "password", created_at: "2026-01-01T00:00:00Z" },
  spaces: { detective: [], informant: [], suspect: [], bulletin_board: [] },
};

const unknownDetective: AnswerView = {
  answer: "不知道", certainty: "unknown", evidence_ids: [], responder: "deterministic",
  trace: { request_id: "detective-miss", query: "密码", searched_scopes: ["detective", "bulletin_board"], hit_cards: [], duration_ms: 1, mode: "degrade" },
};

const knownInformant: AnswerView = {
  answer: "0427", certainty: "known", evidence_ids: ["private-1"], responder: "deterministic",
  trace: { request_id: "informant-hit", query: "密码", searched_scopes: ["informant", "bulletin_board"], hit_cards: [], duration_ms: 1, mode: "degrade" },
};

const knownDetective: AnswerView = {
  answer: "0427", certainty: "known", evidence_ids: ["public-1"], responder: "deterministic",
  trace: { request_id: "detective-hit", query: "密码", searched_scopes: ["detective", "bulletin_board"], hit_cards: [], duration_ms: 1, mode: "degrade" },
};

describe("guideCompletion", () => {
  it("requires the prescribed detective-miss, informant-hit, publish, detective-hit order", () => {
    let guide = recordScriptLoaded(emptyGuideState());
    expect(guideCompletion(base, guide)).toEqual([true, false, false, false]);
    guide = recordInterrogation(guide, "detective", unknownDetective);
    expect(guideCompletion(base, guide)).toEqual([true, true, false, false]);
    guide = recordInterrogation(guide, "informant", knownInformant);
    expect(guideCompletion(base, guide)).toEqual([true, true, false, false]);
    guide = recordPublication(guide);
    expect(guideCompletion(base, guide)).toEqual([true, true, true, false]);
    guide = recordInterrogation(guide, "detective", knownDetective);
    expect(guideCompletion(base, guide)).toEqual([true, true, true, true]);
  });

  it("rebuilds the same guide from replayed domain events and resets it", () => {
    let guide = emptyGuideState();
    const events = [
      { type: "script.loaded", request_id: "script", payload: {} },
      { type: "retrieval.completed", request_id: "detective-miss", payload: { agent_id: "detective" } },
      { type: "answer.completed", request_id: "detective-miss", payload: { certainty: "unknown" } },
      { type: "retrieval.completed", request_id: "informant-hit", payload: { agent_id: "informant" } },
      { type: "answer.completed", request_id: "informant-hit", payload: { certainty: "known" } },
      { type: "memory.published", request_id: "publish", payload: {} },
      { type: "retrieval.completed", request_id: "detective-hit", payload: { agent_id: "detective" } },
      { type: "answer.completed", request_id: "detective-hit", payload: { certainty: "known" } },
    ];
    for (const event of events) guide = applyGuideEvent(guide, event);
    expect(guideCompletion(base, guide)).toEqual([true, true, true, true]);
    guide = applyGuideEvent(guide, { type: "case.reset", request_id: "reset", payload: {} });
    expect(guideCompletion({ ...base, case: { ...base.case, script_id: null, status: "empty" } }, guide)).toEqual([false, false, false, false]);
  });
});
