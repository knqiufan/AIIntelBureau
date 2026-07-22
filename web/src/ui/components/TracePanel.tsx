import type { AgentId, AnswerView, MemoryCard as MemoryCardModel, RetrievalTrace } from "../../types";
import { retrievalResultLabel, retrievalStats, roleLabel } from "../labels";
import { SearchBusy } from "./SearchBusy";

export function TracePanel({
  trace,
  answer,
  searching = false,
}: {
  trace?: RetrievalTrace | null;
  answer?: AnswerView | null;
  searching?: boolean;
}): JSX.Element {
  if (searching) {
    return (
      <section className="trace searching-trace" aria-live="polite">
        <SearchBusy variant="trace" />
        <div className="trace-skeleton" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </section>
    );
  }

  if (!trace) {
    return (
      <section className="trace empty-trace" aria-live="polite">
        <p>尚未发起检索。这里会先显示本次检索范围，再显示回答。</p>
      </section>
    );
  }

  const { covered, hit } = retrievalStats(trace, answer);

  return (
    <section className="trace trace-ready" aria-live="polite">
      <div>
        <span>检索范围</span>
        {trace.searched_scopes.map((scope) => (
          <b key={scope}>{roleLabel(scope)}</b>
        ))}
      </div>
      <div>
        <span>结果</span>
        <b className={hit ? "hit" : "miss"}>{retrievalResultLabel(covered, hit)}</b>
        <small>
          {trace.duration_ms} ms · {trace.mode === "degrade" ? "证据模式" : "角色表达模式"}
        </small>
      </div>
    </section>
  );
}

export function TechnicalDrawer({
  trace,
  answer,
  agentId,
  selectedCard,
}: {
  trace?: RetrievalTrace | null;
  answer?: AnswerView | null;
  agentId: AgentId;
  selectedCard: MemoryCardModel | null;
}): JSX.Element {
  const { covered, hit } = retrievalStats(trace, answer);

  return (
    <details className="technical-drawer">
      <summary>技术抽屉</summary>
      <dl>
        <div>
          <dt>request_id</dt>
          <dd>
            <code>{trace?.request_id ?? "--"}</code>
          </dd>
        </div>
        <div>
          <dt>agent_id</dt>
          <dd>
            <code>{agentId}</code>
          </dd>
        </div>
        <div>
          <dt>memory_id</dt>
          <dd>
            <code>{selectedCard?.id ?? "--"}</code>
          </dd>
        </div>
        <div>
          <dt>trace</dt>
          <dd>
            {trace
              ? `${trace.searched_scopes.join(" + ")} · covered ${covered} · hit ${hit} · ${trace.duration_ms} ms`
              : "--"}
          </dd>
        </div>
      </dl>
    </details>
  );
}
