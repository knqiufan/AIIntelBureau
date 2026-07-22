import type { AgentId } from "../types";

export const roles: {
  id: Exclude<AgentId, "bulletin_board">;
  label: string;
  role: string;
  note: string;
}[] = [
  { id: "detective", label: "侦探", role: "只信亲眼查到的线索", note: "私有检索 + 公告板" },
  { id: "informant", label: "线人", role: "掌握内幕，提供来源", note: "私有检索 + 公告板" },
  { id: "suspect", label: "嫌疑人", role: "只能陈述自己的线索", note: "私有检索 + 公告板" },
];

export const scripts: { id: "password" | "mole" | "allergy"; label: string; description: string }[] = [
  { id: "password", label: "A · 保险箱密码", description: "验证私有秘密如何被显式公开" },
  { id: "mole", label: "B · 谁是内鬼", description: "验证共享情报的质量与来源" },
  { id: "allergy", label: "C · 过敏暗号", description: "生活化的虚构协作场景" },
];

export function shortCaseId(caseId: string): string {
  return caseId.slice(0, 8).toUpperCase();
}

export function roleLabel(agent: AgentId): string {
  if (agent === "detective") return "侦探";
  if (agent === "informant") return "线人";
  if (agent === "suspect") return "嫌疑人";
  return "公告板";
}

export function statusLabel(status: string): string {
  if (status === "ok") return "正常";
  if (status === "degraded") return "证据模式";
  if (status === "unconfigured") return "待配置";
  return "不可用";
}

export function fallbackMessage(reason: string): string {
  if (reason === "APITimeoutError") return "模型响应超时，已用可见证据生成答案。";
  if (reason === "RoleResponseError") return "模型回答未通过证据校验，已用可见证据生成答案。";
  return "模型暂时不可用，已用可见证据生成答案。";
}

/** Distinguish retrieval candidates from citations actually used to answer. */
export function retrievalStats(
  trace?: { hit_cards: unknown[] } | null,
  answer?: { certainty: "known" | "unknown"; evidence_ids: string[] } | null,
): { covered: number; hit: number } {
  const covered = trace?.hit_cards.length ?? 0;
  if (!answer || answer.certainty !== "known") {
    return { covered, hit: 0 };
  }
  return { covered, hit: answer.evidence_ids.length || covered };
}

export function retrievalResultLabel(covered: number, hit: number): string {
  if (hit > 0 && hit === covered) return `命中 ${hit} 条`;
  if (hit > 0) return `覆盖 ${covered} 条，命中 ${hit} 条`;
  if (covered > 0) return `覆盖 ${covered} 条，未命中`;
  return "未命中可见记忆";
}

export function retrievalBadgeLabel(covered: number, hit: number): string {
  if (hit > 0) return `${hit} 命中`;
  if (covered > 0) return `覆盖 ${covered} · 命中 0`;
  return "0 命中";
}
