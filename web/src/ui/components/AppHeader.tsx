import type { Health, Snapshot } from "../../types";
import { shortCaseId, statusLabel } from "../labels";

export function AppHeader({
  snapshot,
  health,
  stage,
  onNewCase,
  onReset,
}: {
  snapshot: Snapshot;
  health: Health | null;
  stage?: boolean;
  onNewCase?: () => void;
  onReset?: () => void;
}): JSX.Element {
  return (
    <header className={`app-header ${stage ? "stage-header" : ""}`}>
      <div className="brand">
        <span className="eyebrow">PowerMem evidence game</span>
        <h1>AI 情报局</h1>
      </div>
      <div className="header-meta">
        <span className="case-chip">案件 {shortCaseId(snapshot.case.case_id)}</span>
        <HealthDot label="记忆" part={health?.seekdb} />
        <HealthDot label="LLM" part={health?.llm} />
        {onReset && (
          <button className="quiet-button" onClick={onReset}>
            重置当前案
          </button>
        )}
        {onNewCase && (
          <button className="quiet-button" onClick={onNewCase}>
            新开案件
          </button>
        )}
      </div>
    </header>
  );
}

function HealthDot({ label, part }: { label: string; part?: Health["llm"] }): JSX.Element {
  return (
    <span className={`health ${part?.status ?? "unconfigured"}`} title={part?.detail ?? "正在检查"}>
      <i aria-hidden="true" />
      {label} · {part ? statusLabel(part.status) : "检查中"}
    </span>
  );
}
