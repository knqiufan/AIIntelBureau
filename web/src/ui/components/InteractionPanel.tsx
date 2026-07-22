import type { AgentId, Health, MemoryCard as MemoryCardModel, Snapshot } from "../../types";
import { roleLabel } from "../labels";
import { AnswerCard } from "./AnswerCard";
import { MemorySpace } from "./MemorySpace";
import { ButtonSpinner } from "./SearchBusy";

export function InteractionPanel({
  snapshot,
  health,
  selectedRole,
  selectedCard,
  question,
  whisper,
  loading,
  onQuestionChange,
  onWhisperChange,
  onSelectCard,
  onAsk,
  onSubmitWhisper,
}: {
  snapshot: Snapshot;
  health: Health | null;
  selectedRole: Exclude<AgentId, "bulletin_board">;
  selectedCard: MemoryCardModel | null;
  question: string;
  whisper: string;
  loading: string | null;
  onQuestionChange: (value: string) => void;
  onWhisperChange: (value: string) => void;
  onSelectCard: (card: MemoryCardModel | null) => void;
  onAsk: (preset?: string) => void;
  onSubmitWhisper: () => void;
}): JSX.Element {
  const loaded = Boolean(snapshot.case.script_id);
  const searching = loading === "ask";

  return (
    <section className="interaction-panel panel" aria-label="局长操作台">
      <div className="panel-title">
        <div>
          <span className="eyebrow">审问对象</span>
          <h2>{roleLabel(selectedRole)}</h2>
        </div>
        <span className={`mode-chip${searching ? " mode-chip-busy" : ""}`}>
          {searching ? "检索中" : health?.mode === "full" ? "角色表达模式" : "证据模式"}
        </span>
      </div>
      <div className={`panel-scroll${loading === "script" ? " is-refreshing" : ""}`}>
        <div className="interaction-zones">
          <div className="target-zone" key={selectedRole}>
            <MemorySpace
              title={`${roleLabel(selectedRole)}的私有记忆`}
              agentId={selectedRole}
              cards={snapshot.spaces[selectedRole]}
              selectedCardId={selectedCard?.id}
              selectable
              onSelect={onSelectCard}
            />
            <WhisperBox
              selectedRole={selectedRole}
              whisper={whisper}
              loading={loading}
              disabled={!loaded}
              onWhisperChange={onWhisperChange}
              onSubmitWhisper={onSubmitWhisper}
            />
          </div>
          <div className="ask-zone">
            {!loaded ? (
              <EmptyAction />
            ) : (
              <>
                <QuickActions selectedRole={selectedRole} loading={loading} onAsk={onAsk} />
                <QuestionComposer
                  question={question}
                  loading={loading}
                  onQuestionChange={onQuestionChange}
                  onAsk={onAsk}
                />
                <AnswerCard answer={snapshot.last_answer} searching={searching} />
              </>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function EmptyAction(): JSX.Element {
  return (
    <div className="empty-action">
      <span className="eyebrow">第一步</span>
      <h2>先加载一份任务</h2>
      <p>选择「A · 保险箱密码」后，三张锁定的私有记忆会出现。接着先问侦探，再问线人。</p>
    </div>
  );
}

function QuickActions({
  selectedRole,
  loading,
  onAsk,
}: {
  selectedRole: Exclude<AgentId, "bulletin_board">;
  loading: string | null;
  onAsk: (preset?: string) => void;
}): JSX.Element {
  const busy = Boolean(loading);
  const searching = loading === "ask";

  return (
    <div className="quick-actions">
      <button disabled={busy} className="primary-button" onClick={() => onAsk("保险箱密码是多少？")}>
        {searching ? (
          <>
            <ButtonSpinner />
            检索中…
          </>
        ) : (
          `问${roleLabel(selectedRole)}密码`
        )}
      </button>
      <button disabled={busy} className="secondary-button" onClick={() => onAsk("你掌握什么情报？")}>
        {searching ? (
          <>
            <ButtonSpinner />
            检索中…
          </>
        ) : (
          "问他掌握什么"
        )}
      </button>
    </div>
  );
}

function QuestionComposer({
  question,
  loading,
  onQuestionChange,
  onAsk,
}: {
  question: string;
  loading: string | null;
  onQuestionChange: (value: string) => void;
  onAsk: (preset?: string) => void;
}): JSX.Element {
  const presets = ["你能证实哪一条线索？", "你的结论来自哪里？", "有哪些公开材料值得复核？"];
  const busy = Boolean(loading);
  const searching = loading === "ask";

  return (
    <section className="question-composer" aria-label="自定义审问编辑器">
      <div className="composer-head">
        <span>自定义审问</span>
        <small>可编辑问题后按 Ctrl / ⌘ + Enter 发送</small>
      </div>
      <div className="question-chips" aria-label="问题灵感">
        {presets.map((preset) => (
          <button key={preset} type="button" disabled={busy} onClick={() => onQuestionChange(preset)}>
            {preset}
          </button>
        ))}
      </div>
      <form
        className="field-label"
        onSubmit={(event) => {
          event.preventDefault();
          if (question.trim()) onAsk();
        }}
      >
        <label htmlFor="interrogation-question">局长的问题</label>
        <textarea
          id="interrogation-question"
          value={question}
          maxLength={300}
          disabled={busy}
          onKeyDown={(event) => {
            if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && question.trim()) {
              event.preventDefault();
              onAsk();
            }
          }}
          onChange={(event) => onQuestionChange(event.target.value)}
        />
        <div className="composer-footer">
          <small>{question.length}/300</small>
          <button disabled={busy || !question.trim()} type="submit">
            {searching ? (
              <>
                <ButtonSpinner />
                检索中…
              </>
            ) : (
              "发送审问"
            )}
          </button>
        </div>
      </form>
    </section>
  );
}

function WhisperBox({
  selectedRole,
  whisper,
  loading,
  disabled,
  onWhisperChange,
  onSubmitWhisper,
}: {
  selectedRole: Exclude<AgentId, "bulletin_board">;
  whisper: string;
  loading: string | null;
  disabled?: boolean;
  onWhisperChange: (value: string) => void;
  onSubmitWhisper: () => void;
}): JSX.Element {
  const sending = loading === "whisper";

  return (
    <form
      className="whisper-box"
      aria-label="耳语编辑器"
      onSubmit={(event) => {
        event.preventDefault();
        if (whisper.trim()) onSubmitWhisper();
      }}
    >
      <div className="whisper-head">
        <span className="eyebrow">对{roleLabel(selectedRole)}耳语</span>
        <small>仅虚构 · 写入后立即出现在上方记忆中</small>
      </div>
      <label className="field-label" htmlFor="whisper-text">
        <span className="sr-only">耳语内容</span>
        <textarea
          id="whisper-text"
          value={whisper}
          maxLength={50}
          rows={2}
          disabled={disabled || sending}
          placeholder={`只让${roleLabel(selectedRole)}一个人知道的情报…`}
          onChange={(event) => onWhisperChange(event.target.value)}
        />
      </label>
      <div className="composer-footer">
        <small>{whisper.length}/50</small>
        <button disabled={disabled || Boolean(loading) || !whisper.trim()} type="submit">
          {sending ? (
            <>
              <ButtonSpinner />
              写入中…
            </>
          ) : (
            "写入私有记忆"
          )}
        </button>
      </div>
    </form>
  );
}
