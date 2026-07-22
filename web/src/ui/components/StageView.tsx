import type { Health, Snapshot } from "../../types";
import { roles, roleLabel } from "../labels";
import { AppHeader } from "./AppHeader";

export function StageView({ snapshot, health }: { snapshot: Snapshot; health: Health | null }): JSX.Element {
  const answer = snapshot.last_answer;
  const verdict = answer
    ? answer.certainty === "known"
      ? `${roleLabel(answer.trace.searched_scopes[0])}命中可见情报`
      : `${roleLabel(answer.trace.searched_scopes[0])}没有命中任何可见记忆`
    : "等待局长加载任务";

  return (
    <main className="stage-shell">
      <AppHeader snapshot={snapshot} health={health} stage />
      <section className="stage-purpose">
        <span className="eyebrow">正在证明</span>
        <h2>{snapshot.case.script_id ? "私有记忆默认隔离；共享必须显式发生" : "每个角色都有自己的私有记忆空间"}</h2>
      </section>
      <section className="stage-characters">
        {roles.map((role) => (
          <article className={`stage-role role-${role.id}`} key={role.id}>
            <span>{role.label}</span>
            <strong>{snapshot.spaces[role.id].length} 条私有记忆</strong>
            <small>仅在自己的检索范围内可见</small>
          </article>
        ))}
        <article className="stage-role role-bulletin_board stage-bulletin">
          <span>公告板</span>
          <strong>{snapshot.spaces.bulletin_board.length} 条公开情报</strong>
          <small>公开副本保留来源</small>
        </article>
      </section>
      <section className="stage-evidence">
        <header>
          <span className="eyebrow">本次检索证据</span>
          <span>{snapshot.last_trace ? `${snapshot.last_trace.duration_ms} ms` : "等待检索"}</span>
        </header>
        {snapshot.last_trace ? (
          <>
            <div className="stage-scopes">
              {snapshot.last_trace.searched_scopes.map((scope) => (
                <b key={scope}>{roleLabel(scope)}</b>
              ))}
            </div>
            <div className="evidence-ticker">
              {answer?.certainty === "known" && snapshot.last_trace.hit_cards.length ? (
                snapshot.last_trace.hit_cards
                  .filter((card) => !answer.evidence_ids.length || answer.evidence_ids.includes(card.id))
                  .map((card) => (
                    <article key={card.id}>
                      <span>{roleLabel(card.owner_agent_id)}</span>
                      <p>{card.content}</p>
                    </article>
                  ))
              ) : (
                <p className="no-hit">未命中可见记忆。这不是系统错误，而是隔离证据。</p>
              )}
            </div>
          </>
        ) : (
          <p className="no-hit">局长的操作会在这里显示可验证的检索范围和命中结果。</p>
        )}
      </section>
      <section className={`verdict ${answer?.certainty ?? "waiting"}`} aria-live="polite">
        <span className="eyebrow">结论</span>
        <h2>{verdict}</h2>
        {answer?.certainty === "known" && <p>{answer.answer}</p>}
      </section>
    </main>
  );
}
