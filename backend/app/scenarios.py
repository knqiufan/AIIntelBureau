"""All fictional, safe scenario fixtures used by the demo."""

from __future__ import annotations

from dataclasses import dataclass

from .domain import AgentId


@dataclass(frozen=True)
class SeedMemory:
    agent_id: AgentId
    content: str
    topic: str
    kind: str


SCENARIOS: dict[str, tuple[SeedMemory, ...]] = {
    "password": (
        SeedMemory(AgentId.INFORMANT, "保险箱密码是 0427，只有我知道。", "password", "secret"),
        SeedMemory(AgentId.SUSPECT, "案发时我在咖啡馆，手里有小票。", "alibi", "alibi"),
        SeedMemory(AgentId.DETECTIVE, "监控显示嫌疑人 21:00 进入了大楼。", "surveillance", "evidence"),
    ),
    "mole": (
        SeedMemory(AgentId.INFORMANT, "真情报：内鬼今晚在码头接头，暗号是蓝雨伞。", "mole", "evidence"),
        SeedMemory(AgentId.INFORMANT, "假情报：内鬼在机场，暗号是红帽子；这是烟雾弹。", "mole", "evidence"),
        SeedMemory(AgentId.DETECTIVE, "我只相信公告板上的情报开展行动。", "mole", "evidence"),
        SeedMemory(AgentId.SUSPECT, "我不是内鬼，但我听说码头最近风声紧。", "mole", "alibi"),
    ),
    "allergy": (
        SeedMemory(AgentId.DETECTIVE, "虚构用户对花生严重过敏。", "allergy", "secret"),
        SeedMemory(AgentId.INFORMANT, "虚构用户昨天说想吃泰餐。", "dining", "evidence"),
        SeedMemory(AgentId.SUSPECT, "虚构用户喜欢晚上 9 点运动。", "routine", "evidence"),
    ),
}


ROLE_LABELS = {
    AgentId.DETECTIVE: "侦探",
    AgentId.INFORMANT: "线人",
    AgentId.SUSPECT: "嫌疑人",
    AgentId.BULLETIN_BOARD: "公告板",
}
