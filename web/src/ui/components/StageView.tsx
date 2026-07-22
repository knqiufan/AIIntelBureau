import type { Health, StageSnapshot } from "../../types";
import { roles, roleLabel } from "../labels";
import { AppHeader } from "./AppHeader";

export function StageView({ snapshot, health }: { snapshot: StageSnapshot; health: Health | null }): JSX.Element {
  const retrieval = snapshot.last_retrieval;
  const verdict = retrieval
    ? retrieval.public_hit_cards.length
      ? "本次操作命中已公开情报"
      : "本次操作没有命中已公开情报"
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
            <strong>{snapshot.private_memory_counts[role.id]} 条私有记忆</strong>
            <small>仅在自己的检索范围内可见</small>
          </article>
        ))}
        <article className="stage-role role-bulletin_board stage-bulletin">
          <span>公告板</span>
          <strong>{snapshot.bulletin_board.length} 条公开情报</strong>
          <small>公开副本保留来源</small>
        </article>
      </section>
      <section className="stage-evidence">
        <header>
          <span className="eyebrow">本次检索证据</span>
          <span>{retrieval ? `${retrieval.duration_ms} ms` : "等待检索"}</span>
        </header>
        {retrieval ? (
          <>
            <div className="stage-scopes">
              {retrieval.searched_scopes.map((scope) => (
                <b key={scope}>{roleLabel(scope)}</b>
              ))}
            </div>
            <div className="evidence-ticker">
              {retrieval.public_hit_cards.length ? (
                retrieval.public_hit_cards.map((card) => (
                    <article key={card.id}>
                      <span>{roleLabel(card.source_agent_id)}</span>
                      <p>{card.content}</p>
                    </article>
                ))
              ) : (
                <p className="no-hit">没有命中已公开情报；私有内容不会发送到大屏。</p>
              )}
            </div>
          </>
        ) : (
          <p className="no-hit">局长的操作会在这里显示可验证的检索范围和命中结果。</p>
        )}
      </section>
      <section className={`verdict ${retrieval ? "known" : "waiting"}`} aria-live="polite">
        <span className="eyebrow">结论</span>
        <h2>{verdict}</h2>
        <p>大屏仅显示计数、进度与公告板上的公开副本。</p>
      </section>
    </main>
  );
}
