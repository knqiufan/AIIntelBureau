import type { AgentId, MemoryCard as MemoryCardModel } from "../../types";
import { BoardIcon, LockIcon } from "../icons";
import { roleLabel } from "../labels";

export function MemorySpace({
  title,
  agentId,
  cards,
  selectedCardId,
  selectable,
  onSelect,
  compact,
  hideHeader,
}: {
  title: string;
  agentId: AgentId;
  cards: MemoryCardModel[];
  selectedCardId?: string;
  selectable: boolean;
  onSelect: (card: MemoryCardModel | null) => void;
  compact?: boolean;
  hideHeader?: boolean;
}): JSX.Element {
  const isBoard = agentId === "bulletin_board";

  return (
    <section className={`memory-space role-${agentId} ${compact ? "compact" : ""}`}>
      {!hideHeader && (
        <header>
          <h3>
            <span className="space-icon" aria-hidden="true">
              {isBoard ? <BoardIcon /> : <LockIcon />}
            </span>
            {title}
          </h3>
          <span>{isBoard ? "公开" : "锁定私有"}</span>
        </header>
      )}
      <div className="memory-space-body">
        {cards.length === 0 ? (
          <p className="space-empty">暂无记忆</p>
        ) : (
          cards.map((card) => (
            <button
              key={card.id}
              aria-pressed={selectedCardId === card.id}
              disabled={!selectable}
              className={`memory-card ${selectedCardId === card.id ? "selected" : ""}`}
              onClick={() => onSelect(selectedCardId === card.id ? null : card)}
            >
              <span>{card.visibility === "public" ? "公开副本" : "私有原件"}</span>
              <p>{card.content}</p>
              {card.source_agent_id && <small>来源：{roleLabel(card.source_agent_id)}</small>}
            </button>
          ))
        )}
      </div>
    </section>
  );
}
