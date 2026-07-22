from __future__ import annotations

from typing import Any, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr

from app.domain import AgentId, Certainty, MemoryCard, MemoryVisibility
from app.role_responder import DeepAgentsRoleResponder
from app.services import AnswerService
from app.settings import Settings


class LocalEvidenceModel(BaseChatModel):
    """A local model that proves the real DeepAgents factory exposes no tools."""

    _bound_tool_sets: list[tuple[str, ...]] = PrivateAttr(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "ai_intel_bureau_local_evidence"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {}

    def _get_ls_params(self, **_: Any) -> dict[str, Any]:
        return {"ls_provider": "ai_intel_bureau_local_evidence"}

    def bind_tools(self, tools: Sequence[Any], *, tool_choice: Any = None, **_: Any) -> "LocalEvidenceModel":
        del tool_choice
        names = tuple(str(getattr(tool, "name", "unknown")) for tool in tools)
        self._bound_tool_sets.append(names)
        if names:
            raise AssertionError(f"role responder must not see tools: {names}")
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **_: Any,
    ) -> ChatResult:
        del messages, stop, run_manager
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content='{"answer":"0427","certainty":"known","evidence_ids":["e1"]}'))])


class PlainTextEvidenceModel(LocalEvidenceModel):
    """Simulates an OpenAI-compatible provider that ignores JSON-only output."""

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **_: Any,
    ) -> ChatResult:
        del messages, stop, run_manager
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="The password is 0427."))])


def evidence_card() -> MemoryCard:
    return MemoryCard(
        id="evidence-1",
        content="保险箱密码是 0427。",
        owner_agent_id=AgentId.INFORMANT,
        visibility=MemoryVisibility.PRIVATE,
        topic="password",
        kind="secret",
    )


def test_deepagents_role_responder_is_tool_free_and_returns_grounded_evidence():
    model = LocalEvidenceModel()
    responder = DeepAgentsRoleResponder(Settings(_env_file=None), model_factory=lambda: model)

    result = responder.answer(AgentId.INFORMANT, "密码是多少？", [evidence_card()])

    assert result.answer == "0427"
    assert result.certainty is Certainty.KNOWN
    assert result.evidence_ids == ["evidence-1"]
    assert all(not tool_set for tool_set in model._bound_tool_sets)


def test_answer_service_uses_grounded_deepagents_result_in_full_mode():
    model = LocalEvidenceModel()
    responder = DeepAgentsRoleResponder(Settings(_env_file=None), model_factory=lambda: model)
    service = AnswerService(Settings(_env_file=None, demo_mode="full", llm_api_key="test-key", demo_external_data_egress_approved=True), role_responder=responder)

    answer = service.answer(AgentId.INFORMANT, "密码是多少？", [evidence_card()])

    assert answer.responder == "deepagents"
    assert answer.evidence_ids == ["evidence-1"]


def test_answer_service_returns_plain_text_provider_content_to_the_client():
    model = PlainTextEvidenceModel()
    responder = DeepAgentsRoleResponder(Settings(_env_file=None), model_factory=lambda: model)
    service = AnswerService(Settings(_env_file=None, demo_mode="full", llm_api_key="test-key", demo_external_data_egress_approved=True), role_responder=responder)

    answer = service.answer(AgentId.INFORMANT, "What is the password?", [evidence_card()])

    assert answer.answer == "The password is 0427."
    assert answer.responder == "deepagents"
    assert answer.fallback_reason is None
    assert answer.evidence_ids == ["evidence-1"]


def test_role_response_replaces_outside_evidence_ids_with_server_owned_packet():
    result = DeepAgentsRoleResponder._parse_payload(
        '{"answer":"0427","certainty":"known","evidence_ids":["not-permitted"]}',
        [evidence_card()],
    )

    assert result.answer == "0427"
    assert result.certainty is Certainty.KNOWN
    assert result.evidence_ids == ["evidence-1"]


def test_role_response_accepts_short_ref_and_numeric_evidence_id():
    card = evidence_card().model_copy(update={"id": "733678205927424000"})

    by_ref = DeepAgentsRoleResponder._parse_payload(
        '{"answer":"0427","certainty":"known","evidence_ids":["e1"]}',
        [card],
    )
    by_numeric = DeepAgentsRoleResponder._parse_payload(
        'Answer follows:\n```json\n'
        '{"answer":"0427","certainty":"known","evidence_ids":[733678205927424000]}\n'
        '```',
        [card],
    )

    assert by_ref.evidence_ids == [card.id]
    assert by_numeric.answer == "0427"
    assert by_numeric.certainty is Certainty.KNOWN
    assert by_numeric.evidence_ids == [card.id]


def test_role_response_recovers_from_corrupted_snowflake_evidence_id():
    card = evidence_card().model_copy(update={"id": "734721210788610048"})

    # Mimic an LLM that rounded a >2^53 identifier while echoing it back.
    result = DeepAgentsRoleResponder._parse_payload(
        '{"answer":"0427","certainty":"known","evidence_ids":[734721210788610000]}',
        [card],
    )

    assert result.answer == "0427"
    assert result.certainty is Certainty.KNOWN
    assert result.evidence_ids == [card.id]


def test_role_response_keeps_a_non_json_answer_with_server_owned_citation():
    result = DeepAgentsRoleResponder._parse_payload("The password is 0427.", [evidence_card()])

    assert result.answer == "The password is 0427."
    assert result.certainty is Certainty.KNOWN
    assert result.evidence_ids == ["evidence-1"]
