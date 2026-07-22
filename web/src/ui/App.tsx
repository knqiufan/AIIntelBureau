import { Component, type ErrorInfo, type ReactNode, useEffect, useState } from "react";
import { ApiError, api } from "../api";
import { applyGuideEvent, emptyGuideState, type GameEvent, type GuideState } from "../lib/guide";
import type { AdvancedFeatures, Health, Snapshot, StageSnapshot } from "../types";
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
  return isStage ? <StageApp caseId={pathCaseId} /> : <OperatorApp initialCaseId={pathCaseId} />;
}

function OperatorApp({ initialCaseId }: { initialCaseId: string | null }): JSX.Element {
  const [caseId, setCaseId] = useState<string | null>(initialCaseId);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [accessRequired, setAccessRequired] = useState(false);
  const [authRevision, setAuthRevision] = useState(0);
  const [loading, setLoading] = useState<string | null>(null);
  const [guide, setGuide] = useState<GuideState>(() => {
    if (!initialCaseId) return emptyGuideState();
    try {
      const saved = sessionStorage.getItem(`ai-intel-bureau:guide:${initialCaseId}`);
      return saved ? { ...emptyGuideState(), ...JSON.parse(saved) } : emptyGuideState();
    } catch {
      return emptyGuideState();
    }
  });
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
    try {
      const saved = sessionStorage.getItem(`ai-intel-bureau:guide:${caseId}`);
      setGuide(saved ? { ...emptyGuideState(), ...JSON.parse(saved) } : emptyGuideState());
    } catch {
      setGuide(emptyGuideState());
    }
    let refreshTimer: number | undefined;
    const queueSnapshotRefresh = () => {
      // A replay can contain many fine-grained events.  Coalesce them into a
      // single snapshot request rather than turning reconnect recovery into a
      // burst of read traffic and UI redraws.
      if (refreshTimer !== undefined) return;
      refreshTimer = window.setTimeout(() => {
        refreshTimer = undefined;
        void refreshSnapshot(caseId).catch(() => undefined);
      }, 120);
    };
    const unsubscribe = api.subscribeEvents(
      caseId,
      (event: GameEvent) => {
        try {
          setGuide((current) => {
            const next = applyGuideEvent(current, event);
            sessionStorage.setItem(`ai-intel-bureau:guide:${caseId}`, JSON.stringify(next));
            return next;
          });
        } catch {
          /* Snapshot refresh remains available. */
        }
        queueSnapshotRefresh();
      },
      (status) => {
        if (status === "error") {
          setError((current) => current ?? "实时同步暂时断开；正在保留当前案件并自动重连。");
        } else {
          setError((current) => (current?.startsWith("实时同步") ? null : current));
        }
      },
    );
    return () => {
      unsubscribe();
      if (refreshTimer !== undefined) window.clearTimeout(refreshTimer);
    };
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
      window.location.assign(`/operate/${created.case.case_id}`);
    });

  const resetCurrentCase = () =>
    run("reset-case", async () => {
      if (!caseId) return;
      setSnapshot(await api.resetCase(caseId, snapshot?.case.version ?? 0));
      setGuide(emptyGuideState());
      sessionStorage.removeItem(`ai-intel-bureau:guide:${caseId}`);
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

  return (
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

function StageApp({ caseId }: { caseId: string | null }): JSX.Element {
  const [snapshot, setSnapshot] = useState<StageSnapshot | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [accessRequired, setAccessRequired] = useState(false);
  const [authRevision, setAuthRevision] = useState(0);

  const refreshSnapshot = async () => {
    if (!caseId) return;
    setSnapshot(await api.stageSnapshot(caseId));
  };

  useEffect(() => {
    if (!caseId) {
      setError("大屏地址缺少案件编号。");
      return;
    }
    void refreshSnapshot().catch((caught) => {
      if (caught instanceof ApiError && (caught.code === "ACCESS_KEY_REQUIRED" || caught.code === "ROLE_FORBIDDEN")) setAccessRequired(true);
      setError(caught instanceof Error ? caught.message : "无法读取大屏快照。");
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, authRevision]);

  useEffect(() => {
    const poll = async () => {
      try { setHealth(await api.health()); } catch { /* health will retry */ }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 10000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!caseId || !snapshot) return;
    let refreshTimer: number | undefined;
    const queueSnapshotRefresh = () => {
      if (refreshTimer !== undefined) return;
      refreshTimer = window.setTimeout(() => {
        refreshTimer = undefined;
        void refreshSnapshot().catch(() => undefined);
      }, 120);
    };
    const unsubscribe = api.subscribeStageEvents(
      caseId,
      queueSnapshotRefresh,
      (status) => {
        if (status === "error") setError((current) => current ?? "实时同步暂时断开；正在自动重连。");
        else setError((current) => (current?.startsWith("实时同步") ? null : current));
      },
    );
    return () => {
      unsubscribe();
      if (refreshTimer !== undefined) window.clearTimeout(refreshTimer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, snapshot?.case.case_id]);

  useEffect(() => {
    if (!caseId || !snapshot) return;
    // SSE is the primary path.  This low-frequency read is a recovery guard
    // for captive networks/proxies that delay an EventSource reconnect.
    const timer = window.setInterval(() => void refreshSnapshot().catch(() => undefined), 1000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, snapshot?.case.case_id]);

  if (accessRequired) {
    return (
      <AccessGate
        role="stage"
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
            setError(caught instanceof Error ? caught.message : "大屏口令验证失败。");
          }
        }}
      />
    );
  }

  if (!snapshot) {
    return (
      <main className="loading-screen">
        <div className="boot-loader" aria-hidden="true"><i className="scan-sweep" /><i className="scan-pulse" /><i className="scan-core" /></div>
        <p>正在连接只读大屏…</p>
        {error && <p className="error-banner">{error}</p>}
      </main>
    );
  }
  return <StageView snapshot={snapshot} health={health} />;
}
