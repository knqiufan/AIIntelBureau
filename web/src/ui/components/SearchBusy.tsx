import { useEffect, useState } from "react";

type SearchBusyVariant = "answer" | "trace" | "inline";

const copy: Record<SearchBusyVariant, { title: string; detail: string; phases: string[] }> = {
  answer: {
    title: "正在检索可见记忆",
    detail: "先扫描角色私有空间与公告板，再组织回答…",
    phases: ["扫描角色私有空间…", "比对公告板公开情报…", "汇总命中证据…", "组织角色化回答…"],
  },
  trace: {
    title: "检索进行中",
    detail: "范围确认与命中结果即将出现",
    phases: ["确认检索范围…", "比对可见记忆…", "记录命中证据…"],
  },
  inline: {
    title: "检索中",
    detail: "",
    phases: [],
  },
};

export function SearchBusy({
  variant = "answer",
  label,
  detail,
}: {
  variant?: SearchBusyVariant;
  label?: string;
  detail?: string;
}): JSX.Element {
  const text = copy[variant];
  const title = label ?? text.title;
  // An explicit detail pins the copy; otherwise phases rotate while waiting.
  const phases = detail ? [] : text.phases;
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    if (phases.length < 2) return undefined;
    const timer = window.setInterval(() => setPhase((current) => (current + 1) % phases.length), 1500);
    return () => window.clearInterval(timer);
  }, [phases.length, variant]);

  const body = detail ?? (phases.length ? phases[phase] : text.detail);

  return (
    <div className={`search-busy search-busy-${variant}`} role="status" aria-live="polite" aria-busy="true">
      <div className="scan-radar" aria-hidden="true">
        <i className="scan-sweep" />
        <i className="scan-pulse" />
        <i className="scan-core" />
      </div>
      <div className="search-busy-copy">
        <strong>{title}</strong>
        {body ? (
          <p key={phases.length ? phase : "pinned"} className="busy-phase">
            {body}
          </p>
        ) : null}
      </div>
      <div className="search-busy-bar" aria-hidden="true">
        <i />
      </div>
    </div>
  );
}

export function ButtonSpinner(): JSX.Element {
  return <span className="button-spinner" aria-hidden="true" />;
}
