"""The only module that talks to the PowerMem Python SDK.

Application services only receive :class:`MemoryGateway`; therefore neither an
API caller nor the LLM can weaken the agent/case filters.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from .domain import AgentId, MemoryCard, MemoryVisibility
from .settings import Settings


def to_user_id(case_id: str) -> str:
    return f"case:{case_id}"


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _result_items(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    if isinstance(result, dict):
        for key in ("results", "memories", "data"):
            items = result.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        if result.get("id") is not None or result.get("memory_id") is not None:
            return [result]
    return []


def card_from_result(raw: dict[str, Any], *, owner: AgentId | None = None) -> MemoryCard:
    metadata = raw.get("metadata") or {}
    raw_owner = owner or raw.get("agent_id") or metadata.get("owner_agent_id")
    card_owner = AgentId(raw_owner)
    visibility = MemoryVisibility(metadata.get("visibility", "public" if card_owner == AgentId.BULLETIN_BOARD else "private"))
    source_agent = metadata.get("source_agent_id") or metadata.get("source_agent")
    memory_id = raw.get("id") or raw.get("memory_id")
    return MemoryCard(
        id=str(memory_id),
        content=str(raw.get("content") or raw.get("memory") or raw.get("document") or ""),
        owner_agent_id=card_owner,
        visibility=visibility,
        topic=str(metadata.get("topic", "general")),
        kind=str(metadata.get("kind", "evidence")),
        score=float(raw["score"]) if raw.get("score") is not None else None,
        source_agent_id=AgentId(source_agent) if source_agent else None,
        source_memory_id=str(metadata["source_memory_id"]) if metadata.get("source_memory_id") is not None else None,
        created_at=_as_datetime(raw.get("created_at")),
    )


class MemoryGateway(Protocol):
    def write_private(self, case_id: str, agent_id: AgentId, content: str, *, topic: str, kind: str, created_by: str) -> MemoryCard: ...

    def write_public(self, case_id: str, source: MemoryCard) -> MemoryCard: ...

    def search_space(self, case_id: str, agent_id: AgentId, query: str) -> list[MemoryCard]: ...

    def list_space(self, case_id: str, agent_id: AgentId) -> list[MemoryCard]: ...

    def get_private(self, case_id: str, agent_id: AgentId, memory_id: str) -> MemoryCard | None: ...

    def delete_card(self, case_id: str, card: MemoryCard) -> None: ...

    def health(self) -> tuple[str, str]: ...


class InMemoryGateway:
    """Deterministic test double; it uses the same filter shape as production."""

    def __init__(self) -> None:
        self._cards: dict[tuple[str, AgentId], list[MemoryCard]] = {}

    @staticmethod
    def _score(query: str, content: str) -> float:
        query_chars = {char for char in query.lower() if char.isalnum() or "\u4e00" <= char <= "\u9fff"}
        if not query_chars:
            return 0.0
        return len(query_chars & set(content.lower())) / len(query_chars)

    def _append(self, case_id: str, card: MemoryCard) -> MemoryCard:
        self._cards.setdefault((case_id, card.owner_agent_id), []).append(card)
        return card

    def write_private(self, case_id: str, agent_id: AgentId, content: str, *, topic: str, kind: str, created_by: str) -> MemoryCard:
        if agent_id == AgentId.BULLETIN_BOARD:
            raise ValueError("private writes require a role")
        return self._append(case_id, MemoryCard(
            id=f"mem_{uuid.uuid4().hex}", content=content, owner_agent_id=agent_id,
            visibility=MemoryVisibility.PRIVATE, topic=topic, kind=kind,
        ))

    def write_public(self, case_id: str, source: MemoryCard) -> MemoryCard:
        return self._append(case_id, MemoryCard(
            id=f"public_{uuid.uuid4().hex}",
            content=f"【公开】{source.content}（来源：{source.owner_agent_id.value}）",
            owner_agent_id=AgentId.BULLETIN_BOARD,
            visibility=MemoryVisibility.PUBLIC,
            topic=source.topic,
            kind="public",
            source_agent_id=source.owner_agent_id,
            source_memory_id=source.id,
        ))

    def search_space(self, case_id: str, agent_id: AgentId, query: str) -> list[MemoryCard]:
        scored = [(self._score(query, card.content), card) for card in self.list_space(case_id, agent_id)]
        return [card.model_copy(update={"score": round(score, 3)}) for score, card in scored if score >= 0.2]

    def list_space(self, case_id: str, agent_id: AgentId) -> list[MemoryCard]:
        return list(self._cards.get((case_id, agent_id), []))

    def get_private(self, case_id: str, agent_id: AgentId, memory_id: str) -> MemoryCard | None:
        return next((card for card in self.list_space(case_id, agent_id) if card.id == memory_id), None)

    def delete_card(self, case_id: str, card: MemoryCard) -> None:
        key = (case_id, card.owner_agent_id)
        self._cards[key] = [item for item in self._cards.get(key, []) if item.id != card.id]

    def health(self) -> tuple[str, str]:
        return "ok", "in-memory test gateway"


class PowerMemSdkGateway:
    """Direct PowerMem Python SDK adapter for OceanBase or embedded seekdb.

    In ``oceanbase`` mode, PowerMem delegates to ``pyobvector`` and its
    MySQL-compatible ``mysql+oceanbase`` driver.  In ``embedded`` mode the
    same SDK receives an empty host and opens the configured local seekdb path.
    The application never calls a PowerMem HTTP endpoint.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._memories: dict[AgentId, Any] = {}

    def _memory(self, agent_id: AgentId) -> Any:
        if agent_id not in self._memories:
            if not self.settings.memory_is_configured:
                if self.settings.seekdb_mode == "oceanbase":
                    raise RuntimeError("remote seekdb requires SEEKDB_HOST, SEEKDB_USER, SEEKDB_DATABASE, EMBEDDING_API_KEY and EMBEDDING_MODEL")
                raise RuntimeError("embedded seekdb requires EMBEDDING_API_KEY and EMBEDDING_MODEL")
            from powermem import create_memory
            self._memories[agent_id] = create_memory(config=self.settings.powermem_config(), agent_id=agent_id.value)
        return self._memories[agent_id]

    def _write(self, case_id: str, agent_id: AgentId, content: str, metadata: dict[str, Any]) -> MemoryCard:
        result = self._memory(agent_id).add(content, user_id=to_user_id(case_id), agent_id=agent_id.value, metadata=metadata, infer=False)
        items = _result_items(result)
        if not items:
            raise RuntimeError("PowerMem SDK did not return a memory card")
        return card_from_result(items[0], owner=agent_id)

    def write_private(self, case_id: str, agent_id: AgentId, content: str, *, topic: str, kind: str, created_by: str) -> MemoryCard:
        return self._write(case_id, agent_id, content, {"case_id": case_id, "visibility": "private", "owner_agent_id": agent_id.value, "topic": topic, "kind": kind, "created_by": created_by, "is_demo_safe": True})

    def write_public(self, case_id: str, source: MemoryCard) -> MemoryCard:
        return self._write(case_id, AgentId.BULLETIN_BOARD, f"【公开】{source.content}（来源：{source.owner_agent_id.value}）", {"case_id": case_id, "visibility": "public", "topic": source.topic, "kind": "public", "source_agent_id": source.owner_agent_id.value, "source_memory_id": source.id, "created_by": "operator", "is_demo_safe": True})

    def search_space(self, case_id: str, agent_id: AgentId, query: str) -> list[MemoryCard]:
        return [card_from_result(item, owner=agent_id) for item in _result_items(self._memory(agent_id).search(query, user_id=to_user_id(case_id), agent_id=agent_id.value, limit=20))]

    def list_space(self, case_id: str, agent_id: AgentId) -> list[MemoryCard]:
        """Read every card using the SDK's explicit offset pagination.

        Never use a capped first page as an authorization, publication, or
        cleanup source.  The application quota keeps active demo spaces below
        100 cards, but this loop also makes legacy/administrative cleanup
        complete when a space pre-dates that boundary.
        """
        raw_cards: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = _result_items(self._memory(agent_id).get_all(
                user_id=to_user_id(case_id), agent_id=agent_id.value,
                limit=self.settings.demo_memory_page_size, offset=offset,
            ))
            raw_cards.extend(page)
            if len(page) < self.settings.demo_memory_page_size:
                break
            offset += len(page)
        # A provider retry can overlap pages; preserve the first result and
        # avoid duplicated cards in snapshots or deletion compensation.
        seen: set[str] = set()
        cards: list[MemoryCard] = []
        for item in raw_cards:
            card = card_from_result(item, owner=agent_id)
            if card.id not in seen:
                seen.add(card.id)
                cards.append(card)
        return cards

    def get_private(self, case_id: str, agent_id: AgentId, memory_id: str) -> MemoryCard | None:
        return next((card for card in self.list_space(case_id, agent_id) if card.id == memory_id), None)

    def delete_card(self, case_id: str, card: MemoryCard) -> None:
        self._memory(card.owner_agent_id).delete(card.id, user_id=to_user_id(case_id), agent_id=card.owner_agent_id.value)

    def health(self) -> tuple[str, str]:
        if not self.settings.memory_is_configured:
            if self.settings.seekdb_mode == "oceanbase":
                return "unconfigured", "set SEEKDB_HOST, SEEKDB_USER, SEEKDB_DATABASE, EMBEDDING_API_KEY and EMBEDDING_MODEL"
            return "unconfigured", "set EMBEDDING_API_KEY and EMBEDDING_MODEL before selecting embedded seekdb"
        try:
            self._memory(AgentId.DETECTIVE)
            detail = "direct OceanBase/MySQL-compatible seekdb connection is initialized" if self.settings.seekdb_mode == "oceanbase" else "embedded seekdb is initialized"
            return "ok", detail
        except Exception as exc:
            return "error", f"PowerMem SDK seekdb is unavailable: {type(exc).__name__}"


def build_gateway(settings: Settings) -> MemoryGateway:
    if settings.demo_memory_adapter == "in_memory":
        return InMemoryGateway()
    return PowerMemSdkGateway(settings)
