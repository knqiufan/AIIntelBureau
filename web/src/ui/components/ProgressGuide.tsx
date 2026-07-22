import { guideCompletion, type GuideState } from "../../lib/guide";
import type { Snapshot } from "../../types";

export function ProgressGuide({ snapshot, guide }: { snapshot: Snapshot; guide: GuideState }): JSX.Element {
  const completion = guideCompletion(snapshot, guide);
  const steps = [
    [completion[0], "加载任务"],
    [completion[1], "验证隔离"],
    [completion[2], "公开情报"],
    [completion[3], "再验证"],
  ] as const;

  return (
    <nav className="progress-guide" aria-label="四步演示进度">
      {steps.map(([done, label], index) => (
        <span key={label} className={done ? "done" : ""}>
          <b>{index + 1}</b>
          {label}
        </span>
      ))}
    </nav>
  );
}

export function CompletionOverlay({ snapshot, guide }: { snapshot: Snapshot; guide: GuideState }): JSX.Element | null {
  if (!guideCompletion(snapshot, guide).every(Boolean)) return null;
  return (
    <section className="completion-overlay" role="status" aria-live="polite">
      <span className="eyebrow">演示完成</span>
      <strong>私有记忆默认隔离；显式公开后，侦探只从公告板副本获得答案。</strong>
    </section>
  );
}
