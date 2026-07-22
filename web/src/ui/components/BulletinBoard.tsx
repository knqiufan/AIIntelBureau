import type { MemoryCard as MemoryCardModel, Snapshot } from "../../types";
import { BoardIcon } from "../icons";
import { MemorySpace } from "./MemorySpace";

export function BulletinBoard({
  snapshot,
  selectedCard,
  loading,
  onSelectCard,
  onPublish,
}: {
  snapshot: Snapshot;
  selectedCard: MemoryCardModel | null;
  loading: string | null;
  onSelectCard: (card: MemoryCardModel | null) => void;
  onPublish: () => void;
}): JSX.Element {
  return (
    <section className="bulletin-panel panel" aria-label="公告板">
      <div className="panel-title bulletin-title">
        <div>
          <span className="eyebrow">公开情报中枢</span>
          <h2>
            <span className="title-icon" aria-hidden="true">
              <BoardIcon />
            </span>
            公告板
          </h2>
        </div>
        <span className="trace-count">{snapshot.spaces.bulletin_board.length} 条公开</span>
      </div>
      <div className="panel-scroll bulletin-scroll">
        <MemorySpace
          title="公告板"
          agentId="bulletin_board"
          cards={snapshot.spaces.bulletin_board}
          selectedCardId={selectedCard?.id}
          selectable={false}
          onSelect={onSelectCard}
          hideHeader
        />
      </div>
      <section className="publication-tray">
        <span className="eyebrow">显式共享</span>
        <p>
          {selectedCard
            ? `将「${selectedCard.content}」复制到公告板；原件会保留。`
            : "选择当前角色的一张私有卡后，才可公开。"}
        </p>
        <button className="publish-button" disabled={!selectedCard || Boolean(loading)} onClick={onPublish}>
          公开到公告板
        </button>
      </section>
    </section>
  );
}
