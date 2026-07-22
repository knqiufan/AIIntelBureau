import { describe, expect, it } from "vitest";
import { retrievalBadgeLabel, retrievalResultLabel, retrievalStats } from "./labels";

describe("retrievalStats", () => {
  it("treats unknown answers as zero hits even when candidates exist", () => {
    expect(
      retrievalStats(
        { hit_cards: [{}, {}, {}, {}, {}] },
        { certainty: "unknown", evidence_ids: [] },
      ),
    ).toEqual({ covered: 5, hit: 0 });
  });

  it("counts known citations as hits", () => {
    expect(
      retrievalStats(
        { hit_cards: [{}, {}, {}] },
        { certainty: "known", evidence_ids: ["a", "b"] },
      ),
    ).toEqual({ covered: 3, hit: 2 });
  });
});

describe("retrieval labels", () => {
  it("explains covered-but-missed retrievals", () => {
    expect(retrievalResultLabel(5, 0)).toBe("覆盖 5 条，未命中");
    expect(retrievalBadgeLabel(5, 0)).toBe("覆盖 5 · 命中 0");
  });

  it("keeps a simple hit label when every candidate is used", () => {
    expect(retrievalResultLabel(2, 2)).toBe("命中 2 条");
    expect(retrievalBadgeLabel(2, 2)).toBe("2 命中");
  });
});
