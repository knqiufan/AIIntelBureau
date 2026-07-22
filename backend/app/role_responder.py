"""Tool-free DeepAgents role phrasing over a server-filtered evidence packet.

This module deliberately owns the DeepAgents integration. It never receives a
gateway, case identifier, or arbitrary tool, so the model cannot widen a
memory query or inspect local/remote resources. The service layer still
validates every cited evidence id before returning an answer to a client.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from .domain import AgentId, Certainty, MemoryCard
from .settings import Settings


BLOCKED_TOOL_NAMES = frozenset({
    "write_todos", "ls", "read_file", "write_file", "edit_file", "glob",
    "grep", "execute", "task",
})


class RoleResponseError(ValueError):
    """A model result was malformed, ungrounded, or unavailable."""


@dataclass(frozen=True)
class RoleResponse:
    answer: str
    certainty: Certainty
    evidence_ids: list[str]


class DeepAgentsRoleResponder:
    """Create one no-tools DeepAgent per role and phrase approved evidence."""

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
        self._agents: dict[AgentId, Any] = {}
        self._profiles_registered: set[str] = set()

    def _model(self) -> Any:
        if self._model_factory:
            return self._model_factory()
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=self.settings.llm_model,
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_base_url,
            temperature=self.settings.llm_temperature,
            timeout=self.settings.llm_timeout_seconds,
            max_retries=0,
            # StepFun is used through its OpenAI Chat Completions-compatible API.
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
        if provider_key in self._profiles_registered:
            return
        from deepagents import GeneralPurposeSubagentProfile, HarnessProfile, register_harness_profile

        register_harness_profile(
            provider_key,
            HarnessProfile(
                base_system_prompt=(
                    "You are a constrained evidence narrator. You have no tools and must never request one. "
                    "Use only the supplied evidence packet. Return exactly one JSON object with "
                    "answer, certainty, and evidence_ids."
                ),
                excluded_tools=BLOCKED_TOOL_NAMES,
                general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
            ),
        )
        self._profiles_registered.add(provider_key)

    def _agent(self, role: AgentId) -> Any:
        if role in self._agents:
            return self._agents[role]
        model = self._model()
        self._register_no_tools_profile(self._provider_key(model))
        if self._agent_creator is None:
            from deepagents import create_deep_agent

            self._agent_creator = create_deep_agent
        agent = self._agent_creator(
            model=model,
            tools=[],
            subagents=[],
            system_prompt=f"You speak only as the {role.value} role in the AI Intelligence Bureau demo.",
            name=f"ai-intel-bureau-{role.value}",
        )
        self._agents[role] = agent
        return agent

    @staticmethod
    def _message_text(message: Any) -> str:
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if not isinstance(item, dict):
                    parts.append(str(item))
                    continue
                text = item.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
                    continue
                # Some OpenAI-compatible providers nest the final answer under
                # content / output_text while keeping reasoning blocks separate.
                nested = item.get("content") or item.get("output_text")
                if isinstance(nested, str) and nested:
                    parts.append(nested)
            return "".join(parts)
        return str(content)

    @staticmethod
    def _json_object(raw: str) -> dict[str, Any] | None:
        """Extract a JSON object when a model adds a harmless prose wrapper.

        Some OpenAI-compatible providers return a short lead-in before an
        otherwise valid object.  The role still receives no tools and the
        result is validated against the server-owned evidence packet below.
        """
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)
        try:
            payload = json.loads(cleaned)
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            pass

        decoder = json.JSONDecoder()
        for match in re.finditer(r"\{", cleaned):
            try:
                payload, _ = decoder.raw_decode(cleaned[match.start():])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        return None

    @staticmethod
    def _citation_map(cards: list[MemoryCard]) -> dict[str, str]:
        """Map short packet refs and real memory ids onto canonical card ids."""
        mapping: dict[str, str] = {}
        for index, card in enumerate(cards, start=1):
            mapping[f"e{index}"] = card.id
            mapping[card.id] = card.id
        return mapping

    @classmethod
    def _evidence_ids(cls, value: Any, cards: list[MemoryCard]) -> list[str]:
        """Normalise citations to server-owned ids; drop anything outside the packet."""
        if value is None:
            return []
        values = value if isinstance(value, list) else [value]
        mapping = cls._citation_map(cards)
        ids: list[str] = []
        for item in values:
            # Providers occasionally serialise numeric-looking memory ids as
            # JSON numbers.  Converting integers is lossless; floats remain
            # rejected because they can lose identifier precision.
            candidate = str(item).strip() if isinstance(item, (str, int)) and not isinstance(item, bool) else ""
            resolved = mapping.get(candidate)
            if resolved and resolved not in ids:
                ids.append(resolved)
        return ids

    @staticmethod
    def _plain_text_response(raw: str, cards: list[MemoryCard]) -> RoleResponse:
        """Keep a useful no-JSON role answer inside the already-filtered scope."""
        answer = re.sub(r"^```(?:text|markdown)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE).strip()
        if not answer:
            raise RoleResponseError("role returned no answer text")
        unknown_markers = ("不知道", "不清楚", "未知", "没有相关", "i don't know", "unknown")
        if any(marker in answer.casefold() for marker in unknown_markers):
            return RoleResponse(answer=answer[:500], certainty=Certainty.UNKNOWN, evidence_ids=[])
        return RoleResponse(answer=answer[:500], certainty=Certainty.KNOWN, evidence_ids=[card.id for card in cards])

    @classmethod
    def _parse_payload(cls, raw: str, cards: list[MemoryCard]) -> RoleResponse:
        payload = cls._json_object(raw)
        if payload is None:
            # The model was given only an approved packet.  Preserve a useful
            # textual answer and let the server attach citations solely from
            # that packet instead of exposing a generic LLM failure to users.
            return cls._plain_text_response(raw, cards)

        answer = str(payload.get("answer", payload.get("content", payload.get("response", "")))).strip()
        if not answer:
            raise RoleResponseError("role returned no answer text")

        certainty_value = str(payload.get("certainty", "")).strip().casefold()
        certainty_aliases = {
            "known": Certainty.KNOWN,
            "知道": Certainty.KNOWN,
            "已知": Certainty.KNOWN,
            "确定": Certainty.KNOWN,
            "unknown": Certainty.UNKNOWN,
            "不知道": Certainty.UNKNOWN,
            "未知": Certainty.UNKNOWN,
            "不确定": Certainty.UNKNOWN,
        }
        certainty = certainty_aliases.get(certainty_value)
        if certainty is None:
            # A usable answer with an approved evidence packet is grounded as
            # known; no cards ever reach this responder for a true miss.
            certainty = Certainty.KNOWN if cards else Certainty.UNKNOWN

        evidence_value = payload.get("evidence_ids", payload.get("evidenceIds", payload.get("citations")))
        evidence_ids = cls._evidence_ids(evidence_value, cards)
        if certainty is Certainty.UNKNOWN:
            evidence_ids = []
        elif not evidence_ids:
            # Citation ownership stays on the server.  Models often mangle
            # large numeric memory ids, so unusable citations are replaced
            # with the already-filtered packet instead of failing the turn.
            evidence_ids = [card.id for card in cards]

        return RoleResponse(answer=answer[:500], certainty=certainty, evidence_ids=evidence_ids)

    def answer(self, role: AgentId, question: str, cards: list[MemoryCard]) -> RoleResponse:
        # Short refs keep large OceanBase/snowflake ids out of the model prompt.
        # LLMs routinely corrupt integers above the 2^53 safe range when they
        # echo them back as JSON numbers.
        evidence = [
            {
                "ref": f"e{index}",
                "content": card.content,
                "scope": card.owner_agent_id.value,
            }
            for index, card in enumerate(cards, start=1)
        ]
        prompt = (
            "Question:\n"
            f"{question}\n\n"
            "Evidence packet (already filtered by the server):\n"
            f"{json.dumps(evidence, ensure_ascii=False)}\n\n"
            "Return JSON only: {\"answer\": string, \"certainty\": \"known\"|\"unknown\", "
            "\"evidence_ids\": [string]}. Cite packet ref values such as \"e1\". "
            "Do not invent refs and do not cite anything outside this packet."
        )
        result = self._agent(role).invoke({"messages": [{"role": "user", "content": prompt}]})
        messages = result.get("messages") if isinstance(result, dict) else None
        if not messages:
            raise RoleResponseError("DeepAgents returned no message")
        return self._parse_payload(self._message_text(messages[-1]), cards)
