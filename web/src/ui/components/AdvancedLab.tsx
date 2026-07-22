import { useEffect, useState } from "react";
import { api } from "../../api";
import type { AdvancedFeatures, AuditTimeline, BoardAnalysis, UnsafeFixture } from "../../types";
import { ChevronIcon, RefreshIcon } from "../icons";
import { roleLabel } from "../labels";
import { ButtonSpinner, SearchBusy } from "./SearchBusy";

export function AdvancedLab({
  caseId,
  version,
  advanced,
}: {
  caseId: string;
  version: number;
  advanced: AdvancedFeatures | null;
}): JSX.Element {
  const [audit, setAudit] = useState<AuditTimeline | null>(null);
  const [analysisQuery, setAnalysisQuery] = useState("保险箱密码");
  const [analysis, setAnalysis] = useState<BoardAnalysis | null>(null);
  const [fixture, setFixture] = useState<UnsafeFixture | null>(null);
  const [confirmUnsafe, setConfirmUnsafe] = useState(false);
  const [busy, setBusy] = useState<"audit" | "analysis" | "fixture" | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const refreshAudit = async () => {
    if (!advanced?.audit_timeline_enabled) return;
    setBusy("audit");
    setMessage(null);
    try {
      setAudit(await api.auditTimeline(caseId));
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "无法读取公开审计时间线。");
    } finally {
      setBusy(null);
    }
  };

  useEffect(() => {
    void refreshAudit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, version, advanced?.audit_timeline_enabled]);

  useEffect(
    () => () => {
      if (fixture) void api.closeUnsafeFixture(fixture.fixture_id);
    },
    [fixture],
  );

  const analyze = async () => {
    if (!analysisQuery.trim()) return;
    setBusy("analysis");
    setMessage(null);
    try {
      setAnalysis(await api.analyzeBoard(caseId, analysisQuery.trim()));
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "公开材料分析未完成。");
    } finally {
      setBusy(null);
    }
  };

  const startFixture = async () => {
    setBusy("fixture");
    setMessage(null);
    try {
      setFixture(await api.startUnsafeFixture());
      setConfirmUnsafe(false);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "无法启动隔离 fixture。");
    } finally {
      setBusy(null);
    }
  };

  const closeFixture = async () => {
    if (!fixture) return;
    setBusy("fixture");
    try {
      await api.closeUnsafeFixture(fixture.fixture_id);
      setFixture(null);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "无法清理隔离 fixture。");
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="advanced-lab" aria-label="P4 高级协作实验室">
      <header className="advanced-head">
        <div>
          <span className="eyebrow">P4 advanced laboratory</span>
          <h2>高级协作实验室</h2>
        </div>
        <span className={`feature-state ${advanced?.enabled ? "on" : "off"}`}>
          {advanced?.enabled ? "已受控开启" : "未开启"}
        </span>
      </header>
      {!advanced?.enabled ? (
        <p className="advanced-muted">当前部署保持 P1–P3 基线；高级能力可通过环境配置逐项开启。</p>
      ) : (
        <LabModules
          advanced={advanced}
          audit={audit}
          analysisQuery={analysisQuery}
          analysis={analysis}
          fixture={fixture}
          confirmUnsafe={confirmUnsafe}
          busy={busy}
          onRefreshAudit={() => void refreshAudit()}
          onQueryChange={setAnalysisQuery}
          onAnalyze={() => void analyze()}
          onConfirmUnsafe={() => setConfirmUnsafe(true)}
          onCancelUnsafe={() => setConfirmUnsafe(false)}
          onStartFixture={() => void startFixture()}
          onCloseFixture={() => void closeFixture()}
        />
      )}
      {message && (
        <p className="lab-message" role="status">
          {message}
        </p>
      )}
    </section>
  );
}

function LabModules({
  advanced,
  audit,
  analysisQuery,
  analysis,
  fixture,
  confirmUnsafe,
  busy,
  onRefreshAudit,
  onQueryChange,
  onAnalyze,
  onConfirmUnsafe,
  onCancelUnsafe,
  onStartFixture,
  onCloseFixture,
}: {
  advanced: AdvancedFeatures;
  audit: AuditTimeline | null;
  analysisQuery: string;
  analysis: BoardAnalysis | null;
  fixture: UnsafeFixture | null;
  confirmUnsafe: boolean;
  busy: "audit" | "analysis" | "fixture" | null;
  onRefreshAudit: () => void;
  onQueryChange: (value: string) => void;
  onAnalyze: () => void;
  onConfirmUnsafe: () => void;
  onCancelUnsafe: () => void;
  onStartFixture: () => void;
  onCloseFixture: () => void;
}): JSX.Element {
  return (
    <>
      <AuditModule
        enabled={advanced.audit_timeline_enabled}
        audit={audit}
        busy={busy === "audit"}
        onRefresh={onRefreshAudit}
      />
      <AnalystModule
        enabled={advanced.board_analysis_enabled}
        analysisQuery={analysisQuery}
        analysis={analysis}
        busy={busy === "analysis"}
        onQueryChange={onQueryChange}
        onAnalyze={async () => onAnalyze()}
      />
      <NativeShareModule enabled={advanced.native_share_experiment_enabled} note={advanced.native_share_note} />
      <UnsafeModule
        enabled={advanced.unsafe_fixture_enabled}
        fixture={fixture}
        confirmUnsafe={confirmUnsafe}
        busy={busy === "fixture"}
        onConfirm={onConfirmUnsafe}
        onCancel={onCancelUnsafe}
        onStart={async () => onStartFixture()}
        onClose={async () => onCloseFixture()}
      />
    </>
  );
}

function AuditModule({
  enabled,
  audit,
  busy,
  onRefresh,
}: {
  enabled: boolean;
  audit: AuditTimeline | null;
  busy: boolean;
  onRefresh: () => void;
}): JSX.Element {
  return (
    <section className="lab-module audit-module">
      <div className="module-title">
        <div>
          <span className="eyebrow">publication audit</span>
          <h3>公开审计时间线</h3>
        </div>
        <button className="icon-button" type="button" disabled={!enabled || busy} aria-label="刷新公开审计时间线" onClick={onRefresh}>
          <RefreshIcon />
        </button>
      </div>
      {!enabled ? (
        <p className="advanced-muted">此部署已关闭审计投影。</p>
      ) : audit?.entries.length ? (
        <ol className="audit-list">
          {audit.entries.map((entry) => (
            <li key={entry.event_id}>
              <time>
                {new Date(entry.created_at).toLocaleTimeString("zh-CN", {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })}
              </time>
              <span>
                <b>{entry.operator}</b> 将 {roleLabel(entry.source_agent_id)} 的私有卡{" "}
                <code>{entry.source_memory_id.slice(0, 10)}</code> 复制为公告板副本{" "}
                <code>{entry.public_card_id.slice(0, 10)}</code>
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="advanced-muted">还没有公开操作。时间线只读取 publication 事件，不扫描私有空间。</p>
      )}
    </section>
  );
}

function AnalystModule({
  enabled,
  analysisQuery,
  analysis,
  busy,
  onQueryChange,
  onAnalyze,
}: {
  enabled: boolean;
  analysisQuery: string;
  analysis: BoardAnalysis | null;
  busy: boolean;
  onQueryChange: (value: string) => void;
  onAnalyze: () => Promise<void>;
}): JSX.Element {
  return (
    <section className="lab-module analyst-module">
      <div className="module-title">
        <div>
          <span className="eyebrow">public evidence only</span>
          <h3>公告板材料分析</h3>
        </div>
        <span className="model-tag">{analysis?.responder ?? "待命"}</span>
      </div>
      {!enabled ? (
        <p className="advanced-muted">部署默认关闭此能力。开启后，两个无工具子 Agent 只接收公告板检索结果。</p>
      ) : (
        <form
          className="analyst-form"
          onSubmit={(event) => {
            event.preventDefault();
            void onAnalyze();
          }}
        >
          <label htmlFor="board-analysis-query">
            向 BureauAnalyst 提问
            <textarea
              id="board-analysis-query"
              value={analysisQuery}
              maxLength={300}
              onChange={(event) => onQueryChange(event.target.value)}
            />
          </label>
          <div className="composer-footer">
            <small>{analysisQuery.length}/300 · 不会读取私有记忆</small>
            <button className="secondary-button" disabled={busy || !analysisQuery.trim()} type="submit">
              {busy ? (
                <>
                  <ButtonSpinner />
                  分析中…
                </>
              ) : (
                "运行公开分析"
              )}
            </button>
          </div>
        </form>
      )}
      {busy ? (
        <div className="analysis-result analysis-busy">
          <SearchBusy
            variant="answer"
            label="正在检索公告板材料"
            detail="只扫描公开情报，不会触碰私有记忆…"
          />
        </div>
      ) : (
        analysis && <AnalysisResult analysis={analysis} />
      )}
    </section>
  );
}

function AnalysisResult({ analysis }: { analysis: BoardAnalysis }): JSX.Element {
  return (
    <div className="analysis-result" aria-live="polite">
      <p className="analysis-notice">{analysis.notice}</p>
      <div className="analysis-columns">
        <section>
          <h4>事实清单</h4>
          {analysis.facts.length ? (
            <ul>
              {analysis.facts.map((fact) => (
                <li key={fact.card_id}>
                  <span>
                    {roleLabel(fact.source_agent_id)} · {fact.topic}
                  </span>
                  {fact.statement}
                </li>
              ))}
            </ul>
          ) : (
            <p>未命中公开材料。</p>
          )}
        </section>
        <section>
          <h4>结构化风险</h4>
          {analysis.risks.length ? (
            <ul>
              {analysis.risks.map((risk, index) => (
                <li key={`${risk.title}-${index}`} className={`risk-${risk.severity}`}>
                  <b>{risk.title}</b>
                  <span>{risk.detail}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p>没有发现需要提示的公开材料冲突。</p>
          )}
        </section>
      </div>
    </div>
  );
}

function NativeShareModule({ enabled, note }: { enabled: boolean; note: string }): JSX.Element {
  return (
    <details className="lab-module native-module">
      <summary>
        <span>
          <b>AgentMemory 原生共享实验</b>
          <small>{enabled ? "开发环境已允许契约探针" : "功能开关关闭，主演示不受影响"}</small>
        </span>
        <i aria-hidden="true">
          <ChevronIcon />
        </i>
      </summary>
      <p>{note}</p>
      <ol>
        <li>私有写入 → native share → 对端检索</li>
        <li>重启 → 对端检索</li>
        <li>撤销 → 对端检索 → 再共享</li>
        <li>失败重试、重复共享与跨 case 隔离</li>
      </ol>
    </details>
  );
}

function UnsafeModule({
  enabled,
  fixture,
  confirmUnsafe,
  busy,
  onConfirm,
  onCancel,
  onStart,
  onClose,
}: {
  enabled: boolean;
  fixture: UnsafeFixture | null;
  confirmUnsafe: boolean;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  onStart: () => Promise<void>;
  onClose: () => Promise<void>;
}): JSX.Element {
  return (
    <section className={`lab-module unsafe-module ${fixture ? "active" : ""}`}>
      <div className="module-title">
        <div>
          <span className="eyebrow">isolated anti-pattern</span>
          <h3>反面教材：unsafe_global_search</h3>
        </div>
        <span className="danger-tag">仅 fixture</span>
      </div>
      {!enabled ? (
        <p className="advanced-muted">默认关闭。它只能在关闭自由耳语后单独启用，且绝不会连接正式 Gateway。</p>
      ) : fixture ? (
        <div className="unsafe-active">
          <p>{fixture.warning}</p>
          <small>
            独立 case：{fixture.case_id} · fixture 命中：{fixture.result_count} 条
          </small>
          <button type="button" className="danger-button" disabled={busy} onClick={() => void onClose()}>
            退出并销毁 fixture
          </button>
        </div>
      ) : !confirmUnsafe ? (
        <button type="button" className="danger-button" onClick={onConfirm}>
          查看隔离错误示例
        </button>
      ) : (
        <div className="unsafe-confirm">
          <p>
            确认仅打开虚构的隔离 fixture？它会演示遗漏 <code>agent_id</code> 的风险，并在退出时清理。
          </p>
          <button type="button" className="danger-button" disabled={busy} onClick={() => void onStart()}>
            确认进入隔离示例
          </button>
          <button type="button" className="quiet-button" onClick={onCancel}>
            取消
          </button>
        </div>
      )}
    </section>
  );
}
