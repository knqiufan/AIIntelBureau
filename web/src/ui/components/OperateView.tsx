import { type Dispatch, type SetStateAction, useState } from "react";
import { api } from "../../api";
import {
  recordInterrogation,
  recordPublication,
  recordScriptLoaded,
  type GuideState,
} from "../../lib/guide";
import type { AdvancedFeatures, AgentId, Health, MemoryCard as MemoryCardModel, Snapshot } from "../../types";
import { AppHeader } from "./AppHeader";
import { BulletinBoard } from "./BulletinBoard";
import { InteractionPanel } from "./InteractionPanel";
import { MemoryLens } from "./MemoryLens";
import { CompletionOverlay, ProgressGuide } from "./ProgressGuide";
import { RoleRail } from "./RoleRail";

export function OperateView({
  snapshot,
  health,
  advanced,
  error,
  loading,
  guide,
  setGuide,
  run,
  setSnapshot,
  onNewCase,
  onReset,
}: {
  snapshot: Snapshot;
  health: Health | null;
  error: string | null;
  loading: string | null;
  advanced: AdvancedFeatures | null;
  guide: GuideState;
  setGuide: Dispatch<SetStateAction<GuideState>>;
  run: (name: string, action: () => Promise<void>) => Promise<void>;
  setSnapshot: (value: Snapshot | ((previous: Snapshot | null) => Snapshot | null)) => void;
  onNewCase: () => void;
  onReset: () => void;
}): JSX.Element {
  const [selectedRole, setSelectedRole] = useState<Exclude<AgentId, "bulletin_board">>("detective");
  const [selectedCard, setSelectedCard] = useState<MemoryCardModel | null>(null);
  const [question, setQuestion] = useState("保险箱密码是多少？");
  const [whisper, setWhisper] = useState("");

  const loadScript = (scriptId: "password" | "mole" | "allergy") =>
    run("script", async () => {
      setSnapshot(await api.loadScript(snapshot.case.case_id, scriptId, snapshot.case.version));
      setGuide(recordScriptLoaded);
      setSelectedCard(null);
    });

  const ask = (preset?: string) =>
    run("ask", async () => {
      const answer = await api.interrogate(snapshot.case.case_id, selectedRole, preset ?? question, snapshot.case.version);
      setSnapshot((current) => (current ? { ...current, last_answer: answer, last_trace: answer.trace } : current));
      setGuide((current) => recordInterrogation(current, selectedRole, answer));
    });

  const submitWhisper = () =>
    run("whisper", async () => {
      if (!whisper.trim()) throw new Error("请输入一条不超过 50 字的虚构情报。");
      const result = await api.whisper(snapshot.case.case_id, selectedRole, whisper.trim(), snapshot.case.version);
      setSnapshot(result.snapshot);
      setWhisper("");
    });

  const publish = () =>
    run("publish", async () => {
      if (!selectedCard) throw new Error("先选择一张当前角色的私有记忆卡。 ");
      const result = await api.publish(snapshot.case.case_id, selectedRole, selectedCard.id, snapshot.case.version);
      setSnapshot(result.snapshot);
      setGuide(recordPublication);
      setSelectedCard(null);
    });

  return (
    <main className="operate-shell">
      <AppHeader snapshot={snapshot} health={health} onNewCase={onNewCase} onReset={onReset} />
      <ProgressGuide snapshot={snapshot} guide={guide} />
      <CompletionOverlay snapshot={snapshot} guide={guide} />
      {error && (
        <div className="error-banner" role="status">
          {error}
        </div>
      )}
      <section className="operate-grid">
        <RoleRail
          snapshot={snapshot}
          selectedRole={selectedRole}
          loading={loading}
          onSelectRole={(role) => {
            setSelectedRole(role);
            setSelectedCard(null);
          }}
          onLoadScript={(scriptId) => void loadScript(scriptId)}
        />
        <section className="work-column">
          <InteractionPanel
            snapshot={snapshot}
            health={health}
            selectedRole={selectedRole}
            selectedCard={selectedCard}
            question={question}
            whisper={whisper}
            loading={loading}
            onQuestionChange={setQuestion}
            onWhisperChange={setWhisper}
            onSelectCard={setSelectedCard}
            onAsk={(preset) => void ask(preset)}
            onSubmitWhisper={() => void submitWhisper()}
          />
          <MemoryLens
            snapshot={snapshot}
            selectedRole={selectedRole}
            selectedCard={selectedCard}
            advanced={advanced}
            loading={loading}
            onSelectCard={setSelectedCard}
          />
        </section>
        <BulletinBoard
          snapshot={snapshot}
          selectedCard={selectedCard}
          loading={loading}
          onSelectCard={setSelectedCard}
          onPublish={() => void publish()}
        />
      </section>
    </main>
  );
}
