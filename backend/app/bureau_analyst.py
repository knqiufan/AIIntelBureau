"""Constrained P4 analysis over an already-filtered public evidence packet.

This module deliberately receives cards, never a gateway or case id.  That
keeps the two DeepAgents subagents incapable of broadening the retrieval scope
through a prompt, a tool call, or an accidental dependency on the game state.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Callable, Literal

from .domain import AgentId, AnalysisRisk, BoardAnalysisView, MemoryCard, MemoryVisibility, PublicFact
from .role_responder import BLOCKED_TOOL_NAMES
from .settings import Settings


SubagentName = Literal["evidence_summarizer", "consistency_reviewer"]


class PublicBoardAnalyst:
    """Run two fixed, tool-free subagents over public bulletin-board cards."""

    def __init__(
        self,
        settings: Settings,
        *,
        model_factory: Callable[[], Any] | None = None,
        agent_creator: Callable[..., Any] | None = None,
    ) -> None:
        self.settings = settings
        self._model_factory = model_factory
        self._agent_creator = agent_creator
        self._agents: dict[SubagentName, Any] = {}
        self._profiles_registered: set[str] = set()

    @staticmethod
    def _assert_public(cards: list[MemoryCard]) -> None:
        if any(card.owner_agent_id is not AgentId.BULLETIN_BOARD or card.visibility is not MemoryVisibility.PUBLIC for card in cards):
            raise ValueError("BureauAnalyst accepts bulletin_board public cards only")

    @staticmethod
    def _evidence(cards: list[MemoryCard]) -> list[dict[str, str]]:
        return [
            {
                "card_id": card.id,
                "statement": card.content,
                "topic": card.topic,
                "source_agent_id": card.source_agent_id.value if card.source_agent_id else "unknown",
            }
            for card in cards
        ]

    def _model(self) -> Any:
        if self._model_factory:
            return self._model_factory()
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=self.settings.llm_model,
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_base_url,
            temperature=0,
            timeout=self.settings.llm_timeout_seconds,
            max_retries=0,
            use_responses_api=False,
        )

    @staticmethod
    def _provider_key(model: Any) -> str:
        try:
            params = model._get_ls_params()
            provider = params.get("ls_provider")
            if isinstance(provider, str) and provider:
                return provider
        except (AttributeError, TypeError, NotImplementedError):
            pass
        return "openai"

    def _register_no_tools_profile(self, provider_key: str) -> None:
        """Disable the DeepAgents general-purpose task path as well as tools."""
        if provider_key in self._profiles_registered:
            return
        from deepagents import GeneralPurposeSubagentProfile, HarnessProfile, register_harness_profile

        register_harness_profile(
            provider_key,
            HarnessProfile(
                base_system_prompt=(
                    "You are a constrained public-evidence analyst. You have no tools and must never request one. "
                    "Use only the supplied bulletin-board evidence packet and return the requested JSON."
                ),
                excluded_tools=BLOCKED_TOOL_NAMES,
                general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
            ),
        )
        self._profiles_registered.add(provider_key)

    def _agent(self, name: SubagentName) -> Any:
        if name in self._agents:
            return self._agents[name]
        if self._agent_creator is None:
            from deepagents import create_deep_agent

            self._agent_creator = create_deep_agent
        system_prompt = (
            "You are the AI Intelligence Bureau public-material subagent "
            f"{name}. You have no tools and must not request tools. "
            "Use only the supplied bulletin-board evidence packet. "
        )
        if name == "evidence_summarizer":
            system_prompt += "Return JSON only: {\"facts\":[{\"card_id\":string,\"statement\":string,\"topic\":string,\"source_agent_id\":string}]}."
        else:
            system_prompt += "Return JSON only: {\"risks\":[{\"severity\":\"low\"|\"medium\"|\"high\",\"title\":string,\"detail\":string,\"related_card_ids\":[string]}]}."
        model = self._model()
        self._register_no_tools_profile(self._provider_key(model))
        agent = self._agent_creator(
            model=model,
            tools=[],
            subagents=[],
            name=f"ai-intel-bureau-{name}",
            system_prompt=system_prompt,
        )
        self._agents[name] = agent
        return agent

    @staticmethod
    def _message_text(result: Any) -> str:
        messages = result.get("messages") if isinstance(result, dict) else None
        if not messages:
            raise ValueError("public-material subagent returned no message")
        content = getattr(messages[-1], "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in content)
        return str(content)

    @staticmethod
    def _json(raw: str) -> dict[str, Any]:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)
        value = json.loads(cleaned)
        if not isinstance(value, dict):
            raise ValueError("public-material subagent response must be an object")
        return value

    @staticmethod
    def _facts(value: dict[str, Any], cards: list[MemoryCard]) -> list[PublicFact]:
        allowed = {card.id: card for card in cards}
        facts: list[PublicFact] = []
        for item in value.get("facts", []):
            if not isinstance(item, dict) or str(item.get("card_id")) not in allowed:
                raise ValueError("subagent cited a card outside the public evidence packet")
            card = allowed[str(item["card_id"])]
            facts.append(PublicFact(
                card_id=card.id,
                statement=str(item.get("statement") or card.content)[:500],
                topic=str(item.get("topic") or card.topic)[:80],
                source_agent_id=card.source_agent_id or AgentId.BULLETIN_BOARD,
            ))
        return facts

    @staticmethod
    def _risks(value: dict[str, Any], cards: list[MemoryCard]) -> list[AnalysisRisk]:
        allowed = {card.id for card in cards}
        risks: list[AnalysisRisk] = []
        for item in value.get("risks", []):
            if not isinstance(item, dict):
                continue
            ids = item.get("related_card_ids", [])
            if not isinstance(ids, list) or not all(isinstance(card_id, str) and card_id in allowed for card_id in ids):
                raise ValueError("subagent risk cited a card outside the public evidence packet")
            severity = str(item.get("severity", "low"))
            if severity not in {"low", "medium", "high"}:
                raise ValueError("subagent risk severity is invalid")
            risks.append(AnalysisRisk(
                severity=severity,
                title=str(item.get("title", "公开材料提示"))[:120],
                detail=str(item.get("detail", "请由局长核验公开材料。"))[:500],
                related_card_ids=ids,
            ))
        return risks

    @staticmethod
    def _deterministic(cards: list[MemoryCard]) -> tuple[list[PublicFact], list[AnalysisRisk]]:
        facts = [
            PublicFact(card_id=card.id, statement=card.content, topic=card.topic, source_agent_id=card.source_agent_id or AgentId.BULLETIN_BOARD)
            for card in cards
        ]
        by_topic: dict[str, list[MemoryCard]] = defaultdict(list)
        for card in cards:
            by_topic[card.topic].append(card)
        risks: list[AnalysisRisk] = []
        for topic, topic_cards in by_topic.items():
            distinct_statements = {card.content for card in topic_cards}
            if len(distinct_statements) > 1:
                risks.append(AnalysisRisk(
                    severity="medium",
                    title=f"“{topic}”存在多条公开说法",
                    detail="公开材料对同一主题包含不同陈述；请局长核验来源后再行动。",
                    related_card_ids=[card.id for card in topic_cards],
                ))
        if not facts:
            risks.append(AnalysisRisk(
                severity="low",
                title="没有命中公开材料",
                detail="分析器没有读取私有空间；请调整问题或先显式公开一条材料。",
            ))
        return facts, risks

    def analyze(self, query: str, cards: list[MemoryCard]) -> BoardAnalysisView:
        self._assert_public(cards)
        # In evidence mode the deterministic path is intentional: it remains
        # useful offline and retains the same public-only boundary.
        if not self.settings.llm_is_configured:
            facts, risks = self._deterministic(cards)
            return BoardAnalysisView(query=query, facts=facts, risks=risks, responder="deterministic")

        evidence = json.dumps(self._evidence(cards), ensure_ascii=False)
        try:
            facts_payload = self._json(self._message_text(self._agent("evidence_summarizer").invoke({"messages": [{"role": "user", "content": f"Question: {query}\nPublic evidence: {evidence}"}]})))
            risks_payload = self._json(self._message_text(self._agent("consistency_reviewer").invoke({"messages": [{"role": "user", "content": f"Question: {query}\nPublic evidence: {evidence}"}]})))
            return BoardAnalysisView(
                query=query,
                facts=self._facts(facts_payload, cards),
                risks=self._risks(risks_payload, cards),
                responder="deepagents",
            )
        except Exception:
            # This is a presentation aid. An unavailable model must not cause a
            # live demo to call a broader source or hide the audited evidence.
            facts, risks = self._deterministic(cards)
            return BoardAnalysisView(query=query, facts=facts, risks=risks, responder="deterministic")


# Retain the blocked tool inventory beside the P4 implementation so a future
# refactor cannot accidentally turn either subagent into a task-capable agent.
assert "task" in BLOCKED_TOOL_NAMES
