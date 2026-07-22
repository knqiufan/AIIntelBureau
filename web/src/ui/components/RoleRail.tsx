import type { AgentId, Snapshot } from "../../types";
import { roles, scripts } from "../labels";
import { ButtonSpinner } from "./SearchBusy";

export function RoleRail({
  snapshot,
  selectedRole,
  loading,
  onSelectRole,
  onLoadScript,
}: {
  snapshot: Snapshot;
  selectedRole: Exclude<AgentId, "bulletin_board">;
  loading: string | null;
  onSelectRole: (role: Exclude<AgentId, "bulletin_board">) => void;
  onLoadScript: (scriptId: "password" | "mole" | "allergy") => void;
}): JSX.Element {
  return (
    <aside className="role-rail panel" aria-label="角色与剧本">
      <div className="panel-scroll">
        <h2>选择审问对象</h2>
        {roles.map((role) => (
          <button
            key={role.id}
            className={`role-button role-${role.id} ${selectedRole === role.id ? "selected" : ""}`}
            onClick={() => onSelectRole(role.id)}
          >
            <strong>{role.label}</strong>
            <span>{role.role}</span>
            <small>{role.note}</small>
          </button>
        ))}
        <section className="script-picker">
          <h2>
            任务剧本
            {loading === "script" && <ButtonSpinner />}
          </h2>
          {scripts.map((script) => (
            <button
              key={script.id}
              disabled={Boolean(loading)}
              className={snapshot.case.script_id === script.id ? "selected-script" : ""}
              onClick={() => onLoadScript(script.id)}
            >
              <strong>{script.label}</strong>
              <span>{script.description}</span>
            </button>
          ))}
        </section>
      </div>
    </aside>
  );
}
