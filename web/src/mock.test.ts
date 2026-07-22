import { describe, expect, it } from "vitest";
import { createMockApi } from "./mock";

describe("P1 fixture mock API", () => {
  it("replays the password isolation flow through a controllable event source", async () => {
    const values = new Map<string, string>();
    const storage = { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value) };
    const api = createMockApi(0, storage);
    const created = await api.createCase();
    const events: string[] = [];
    const unsubscribe = api.subscribeEvents(created.case.case_id, (event) => events.push(event.type), () => undefined);

    const loaded = await api.loadScript(created.case.case_id, "password", created.case.version);
    const detective = await api.interrogate(created.case.case_id, "detective", "保险箱密码是多少？", loaded.case.version);
    const informant = await api.interrogate(created.case.case_id, "informant", "保险箱密码是多少？", loaded.case.version);
    const published = await api.publish(created.case.case_id, "informant", "p1-informant-password", loaded.case.version);
    const detectiveAfterPublish = await api.interrogate(created.case.case_id, "detective", "保险箱密码是多少？", published.snapshot.case.version);
    const audit = await api.auditTimeline(created.case.case_id);
    const analysis = await api.analyzeBoard(created.case.case_id, "保险箱密码");

    await new Promise((resolve) => setTimeout(resolve, 0));
    unsubscribe();

    expect(detective.certainty).toBe("unknown");
    expect(informant.certainty).toBe("known");
    expect(detectiveAfterPublish.trace.hit_cards).toHaveLength(1);
    expect(detectiveAfterPublish.trace.hit_cards[0]).toMatchObject({ owner_agent_id: "bulletin_board", source_memory_id: "p1-informant-password" });
    expect(events).toEqual(expect.arrayContaining(["script.loaded", "retrieval.completed", "answer.completed", "memory.published"]));
    expect(audit.entries).toHaveLength(1);
    expect(analysis.facts).toMatchObject([{ source_agent_id: "informant", topic: "password" }]);
  });
});
