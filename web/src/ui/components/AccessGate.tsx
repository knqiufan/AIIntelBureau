import { useState } from "react";

export function AccessGate({
  error,
  onSubmit,
}: {
  error: string | null;
  onSubmit: (key: string) => Promise<void>;
}): JSX.Element {
  const [key, setKey] = useState("");
  const [submitting, setSubmitting] = useState(false);

  return (
    <main className="loading-screen access-gate">
      <section className="access-card">
        <span className="eyebrow">活动访问</span>
        <h1>输入活动口令</h1>
        <p>口令只保存在当前浏览器会话中，用于连接操作端和大屏端。</p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (!key.trim()) return;
            setSubmitting(true);
            void onSubmit(key).finally(() => setSubmitting(false));
          }}
        >
          <label className="field-label">
            活动口令
            <input
              autoFocus
              value={key}
              onChange={(event) => setKey(event.target.value)}
              type="password"
              autoComplete="current-password"
            />
          </label>
          <button className="primary-button" type="submit" disabled={!key.trim() || submitting}>
            {submitting ? "验证中…" : "进入演示"}
          </button>
        </form>
        {error && (
          <p className="error-banner" role="status">
            {error}
          </p>
        )}
      </section>
    </main>
  );
}
