import { Component, type ErrorInfo, type ReactNode, useEffect, useState } from "react";
import { ApiError, api } from "../api";
import { applyGuideEvent, emptyGuideState, type GameEvent, type GuideState } from "../lib/guide";
import type { AdvancedFeatures, Health, Snapshot } from "../types";
import { AccessGate } from "./components/AccessGate";
import { OperateView } from "./components/OperateView";
import { StageView } from "./components/StageView";

class UiErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  componentDidCatch(_: Error, __: ErrorInfo): void {
    // The stage never exposes browser stack traces to an audience.
  }

  render(): ReactNode {
    if (this.state.failed) {
      return (
        <main className="fatal">
          <h1>画面需要恢复</h1>
          <p>刷新页面后会从案件快照重新同步。</p>
          <button onClick={() => window.location.reload()}>刷新画面</button>
        </main>
      );
    }
    return this.props.children;
  }
}

export function App(): JSX.Element {
  return (
    <UiErrorBoundary>
      <BureauApp />
    </UiErrorBoundary>
  );
}

function BureauApp(): JSX.Element {
  const path = window.location.pathname;
  const isStage = path.startsWith("/stage/");
  const pathCaseId = path.match(/\/(?:operate|stage)\/([^/]+)/)?.[1] ?? null;
  const [caseId, setCaseId] = useState<string | null>(pathCaseId);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [accessRequired, setAccessRequired] = useState(false);
  const [authRevision, setAuthRevision] = useState(0);
  const [loading, setLoading] = useState<string | null>(null);
  const [guide, setGuide] = useState<GuideState>(emptyGuideState);
  const [advanced, setAdvanced] = useState<AdvancedFeatures | null>(null);

  const refreshSnapshot = async (id = caseId) => {
    if (!id) return;
    setSnapshot(await api.snapshot(id));
  };

  useEffect(() => {
    const bootstrap = async () => {
      try {
        setError(null);
        if (caseId) {
          await refreshSnapshot(caseId);
          return;
        }
        const created = await api.createCase();
        window.history.replaceState(null, "", `/operate/${created.case.case_id}`);
        setSnapshot(created);
        setCaseId(created.case.case_id);
      } catch (caught) {
        if (caught instanceof ApiError && caught.code === "ACCESS_KEY_REQUIRED") setAccessRequired(true);
        setError(caught instanceof Error ? caught.message : "无法创建案件。");
      }
    };
    void bootstrap();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, authRevision]);

  useEffect(() => {
    const poll = async () => {
      try {
        setHealth(await api.health());
      } catch {
        /* health will retry */
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 10000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    void api.advancedStatus().then(setAdvanced).catch(() => setAdvanced(null));
  }, [authRevision]);

  useEffect(() => {
    if (!caseId) return;
    setGuide(emptyGuideState());
    const unsubscribe = api.subscribeEvents(
      caseId,
      (event: GameEvent) => {
        try {
          setGuide((current) => applyGuideEvent(current, event));
        } catch {
          /* Snapshot refresh remains available. */
        }
        void refreshSnapshot(caseId).catch(() => undefined);
      },
      (status) => {
        if (status === "error") {
          setError((current) => current ?? "实时同步暂时断开；正在保留当前案件并自动重连。");
        } else {
          setError((current) => (current?.startsWith("实时同步") ? null : current));
        }
      },
    );
    return unsubscribe;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  const run = async (name: string, action: () => Promise<void>) => {
    setLoading(name);
    setError(null);
    try {
      await action();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "操作未完成，请重试。");
    } finally {
      setLoading(null);
    }
  };

  const startNewCase = () =>
    run("new-case", async () => {
      const created = await api.createCase();
      window.location.assign(isStage ? `/stage/${created.case.case_id}` : `/operate/${created.case.case_id}`);
    });

  const resetCurrentCase = () =>
    run("reset-case", async () => {
      if (!caseId) return;
      setSnapshot(await api.resetCase(caseId, snapshot?.case.version ?? 0));
      setGuide(emptyGuideState());
    });

  if (!snapshot) {
    if (accessRequired) {
      return (
        <AccessGate
          error={error}
          onSubmit={async (key) => {
            api.setActivityKey(key);
            try {
              await api.establishActivitySession();
              setError(null);
              setAccessRequired(false);
              setAuthRevision((value) => value + 1);
            } catch (caught) {
              setAccessRequired(true);
              setError(caught instanceof Error ? caught.message : "活动口令验证失败。");
            }
          }}
        />
      );
    }
    return (
      <main className="loading-screen">
        <div className="boot-loader" aria-hidden="true">
          <i className="scan-sweep" />
          <i className="scan-pulse" />
          <i className="scan-core" />
        </div>
        <p>正在建立独立案件空间…</p>
        {error && <p className="error-banner">{error}</p>}
      </main>
    );
  }

  return isStage ? (
    <StageView snapshot={snapshot} health={health} />
  ) : (
    <OperateView
      snapshot={snapshot}
      health={health}
      advanced={advanced}
      error={error}
      loading={loading}
      guide={guide}
      setGuide={setGuide}
      run={run}
      setSnapshot={setSnapshot}
      onNewCase={startNewCase}
      onReset={resetCurrentCase}
    />
  );
}
