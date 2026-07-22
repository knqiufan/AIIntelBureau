import type { AdvancedFeatures, AgentId, MemoryCard as MemoryCardModel, Snapshot } from "../../types";
import { retrievalBadgeLabel, retrievalStats, roles } from "../labels";
import { AdvancedLab } from "./AdvancedLab";
import { MemorySpace } from "./MemorySpace";
import { TechnicalDrawer, TracePanel } from "./TracePanel";

export function MemoryLens({
  snapshot,
  selectedRole,
  selectedCard,
  advanced,
  loading = null,
  onSelectCard,
}: {
  snapshot: Snapshot;
  selectedRole: Exclude<AgentId, "bulletin_board">;
  selectedCard: MemoryCardModel | null;
  advanced: AdvancedFeatures | null;
  loading?: string | null;
  onSelectCard: (card: MemoryCardModel | null) => void;
}): JSX.Element {
  const searching = loading === "ask";
  const { covered, hit } = retrievalStats(snapshot.last_trace, snapshot.last_answer);

  return (
    <section className="lens-panel panel" aria-label="记忆透视面板">
      <div className="panel-title">
        <div>
          <span className="eyebrow">后端检索证据</span>
          <h2>记忆透视</h2>
        </div>
        <span className={`trace-count${searching ? " trace-count-busy" : ""}`}>
          {searching ? "检索中…" : retrievalBadgeLabel(covered, hit)}
        </span>
      </div>
      <div className={`panel-scroll${loading === "script" ? " is-refreshing" : ""}`}>
        <TracePanel trace={snapshot.last_trace} answer={snapshot.last_answer} searching={searching} />
        <TechnicalDrawer
          trace={snapshot.last_trace}
          answer={snapshot.last_answer}
          agentId={selectedRole}
          selectedCard={selectedCard}
        />
        <div className="spaces-heading">
          <span className="eyebrow">其他角色的私有空间</span>
          <small>当前对象的记忆已并入左侧审问区</small>
        </div>
        <div className="spaces private-spaces">
          {roles
            .filter((space) => space.id !== selectedRole)
            .map((space) => (
              <MemorySpace
                key={space.id}
                title={space.label}
                agentId={space.id}
                cards={snapshot.spaces[space.id]}
                selectedCardId={selectedCard?.id}
                selectable={false}
                onSelect={onSelectCard}
                compact
              />
            ))}
        </div>
        {advanced?.enabled && (
          <AdvancedLab caseId={snapshot.case.case_id} version={snapshot.case.version} advanced={advanced} />
        )}
      </div>
    </section>
  );
}
