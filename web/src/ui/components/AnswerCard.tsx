import type { AnswerView } from "../../types";
import { fallbackMessage } from "../labels";
import { SearchBusy } from "./SearchBusy";

export function AnswerCard({
  answer,
  searching = false,
}: {
  answer?: AnswerView | null;
  searching?: boolean;
}): JSX.Element {
  if (searching) {
    return (
      <section className="answer-card searching" aria-live="polite">
        <SearchBusy variant="answer" />
      </section>
    );
  }

  if (!answer) {
    return (
      <section className="answer-card waiting" aria-live="polite">
        <span className="eyebrow">回答区</span>
        <p>审问后，这里会在检索证据出现后展示回答。</p>
      </section>
    );
  }

  const known = answer.certainty === "known";

  return (
    <section className={`answer-card ${answer.certainty} answer-ready`} aria-live="polite">
      <div>
        <span className="eyebrow">{known ? "已基于可见证据作答" : "未命中可见记忆"}</span>
        <strong>{known ? "知道" : "不知道"}</strong>
      </div>
      {known && <p>{answer.answer}</p>}
      {known && answer.evidence_ids.length > 0 && (
        <div className="citation-row">
          证据 {answer.evidence_ids.map((id) => <code key={id}>{id.slice(0, 10)}</code>)}
        </div>
      )}
      {answer.fallback_reason && <small>{fallbackMessage(answer.fallback_reason)}</small>}
    </section>
  );
}
