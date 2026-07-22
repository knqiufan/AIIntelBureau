"""Application services: commands pass through fixed case and visibility rules."""

from __future__ import annotations

import threading
import time
import uuid
import re
from dataclasses import dataclass
from typing import Any

from .domain import (
    AdvancedFeaturesView, AgentId, AnswerView, AuditEntry, AuditTimeline,
    BoardAnalysisView, CaseSnapshot, CaseState, Certainty, DomainEvent,
    HealthPart, HealthView, MemoryCard, PublicMemoryCard, PublicSnapshot,
    ROLE_IDS, RetrievalTrace, StageEvent, StageRetrievalView, StageSnapshot,
    UnsafeFixtureView,
)
from .bureau_analyst import PublicBoardAnalyst
from .memory import MemoryGateway
from .observability import get_logger, request_id_context
from .repository import CaseNotFoundError, StateRepository, VersionConflictError
from .role_responder import DeepAgentsRoleResponder, RoleResponse
from .scenarios import SCENARIOS
from .settings import Settings
from .unsafe_fixture import UnsafeFixtureLab


class AccessViolationError(PermissionError):
    pass


class FreeformDisabledError(RuntimeError):
    pass


class UnsafeWhisperError(ValueError):
    """Raised without echoing a potentially sensitive operator input."""

    pass


class WhisperRateLimitError(RuntimeError):
    pass


class MemoryUnavailableError(RuntimeError):
    pass


class AdvancedFeatureDisabledError(RuntimeError):
    """A P4 route was called while its explicit deployment flag is off."""

    pass


@dataclass(frozen=True)
class ResponderResult:
    answer: str
    certainty: Certainty
    evidence_ids: list[str]
    responder: str
    fallback_reason: str | None = None


class AnswerService:
    """LLM presentation is optional and is never allowed to select evidence."""

    def __init__(self, settings: Settings, role_responder: DeepAgentsRoleResponder | None = None) -> None:
        self.settings = settings
        self.role_responder = role_responder or DeepAgentsRoleResponder(settings)

    def deterministic(self, cards: list[MemoryCard]) -> ResponderResult:
        if not cards:
            return ResponderResult("我不知道；当前可见记忆中没有这方面的情报。", Certainty.UNKNOWN, [], "deterministic")
        card = cards[0]
        return ResponderResult(f"根据当前可见情报：{card.content}", Certainty.KNOWN, [card.id], "deterministic")

    def answer(self, role: AgentId, question: str, cards: list[MemoryCard]) -> ResponderResult:
        if not cards or not self.settings.llm_is_configured:
            return self.deterministic(cards)
        try:
            response: RoleResponse = self.role_responder.answer(role, question, cards)
            return ResponderResult(response.answer, response.certainty, response.evidence_ids, "deepagents")
        except Exception as exc:
            get_logger().warning(
                "role.responder_fallback",
                extra={
                    "failure_type": type(exc).__name__,
                    "mode": self.settings.demo_mode,
                },
            )
            fallback = self.deterministic(cards)
            return ResponderResult(fallback.answer, fallback.certainty, fallback.evidence_ids, "deterministic", type(exc).__name__)


class BureauService:
    """The only command coordinator for the game domain."""

    def __init__(self, settings: Settings, gateway: MemoryGateway, repository: StateRepository) -> None:
        self.settings = settings
        self.gateway = gateway
        self.repository = repository
        self.answers = AnswerService(settings)
        self.board_analyst = PublicBoardAnalyst(settings)
        self.unsafe_fixture_lab = UnsafeFixtureLab()
        self._command_lock = threading.RLock()
        self._last_answers: dict[str, AnswerView] = {}
        self._whisper_timestamps: dict[tuple[str, AgentId], list[float]] = {}
        self._logger = get_logger()

    @staticmethod
    def _request_id(incoming: str | None = None) -> str:
        return incoming or request_id_context.get() or f"req_{uuid.uuid4().hex}"

    @staticmethod
    def _event_payload(**values: Any) -> dict[str, Any]:
        return values

    @staticmethod
    def _card_event_payload(card: MemoryCard) -> dict[str, Any]:
        """Keep event/SSE records useful without persisting a free-form card body."""
        return {
            "card_id": card.id,
            "owner_agent_id": card.owner_agent_id.value,
            "visibility": card.visibility.value,
            "topic": card.topic,
            "kind": card.kind,
            "source_agent_id": card.source_agent_id.value if card.source_agent_id else None,
            "source_memory_id": card.source_memory_id,
        }

    def _append(self, case_id: str, event_type: str, request_id: str, **payload: Any) -> DomainEvent:
        event = self.repository.append_event(case_id, event_type, request_id, self._event_payload(**payload))
        self._logger.info("domain.event", extra={"case_id": case_id, "request_id": request_id, "event_type": event_type, "mode": self.settings.demo_mode})
        return event

    def _require_version(self, case: CaseState, expected_version: int) -> None:
        if case.version != expected_version:
            raise VersionConflictError(case.case_id)

    def create_case(self, request_id: str | None = None) -> CaseSnapshot:
        with self._command_lock:
            health_status, _ = self.gateway.health()
            if health_status != "ok":
                raise MemoryUnavailableError("memory storage is not ready; check /api/healthz and configuration")
            case = CaseState(case_id=str(uuid.uuid4()))
            self.repository.create_case(case)
            request_id = self._request_id(request_id)
            self._append(case.case_id, "case.created", request_id, version=case.version, status=case.status)
            return self.snapshot(case.case_id)

    def _advance(self, case: CaseState, expected_version: int, *, script_id: str | None = None, status: str | None = None) -> CaseState:
        self._require_version(case, expected_version)
        updated = case.model_copy(update={
            "version": case.version + 1,
            "script_id": script_id if script_id is not None else case.script_id,
            "status": status if status is not None else case.status,
        })
        return self.repository.update_case(updated, expected_version)

    def load_script(self, case_id: str, script_id: str, expected_version: int, request_id: str | None = None) -> CaseSnapshot:
        if script_id not in SCENARIOS:
            raise ValueError("unknown script")
        with self._command_lock:
            case = self.repository.get_case(case_id)
            self._require_version(case, expected_version)
            if case.script_id == script_id:
                return self.snapshot(case_id)
            request_id = self._request_id(request_id)
            cards: list[MemoryCard] = []
            for seed in SCENARIOS[script_id]:
                card = self.gateway.write_private(case_id, seed.agent_id, seed.content, topic=seed.topic, kind=seed.kind, created_by="script")
                cards.append(card)
                self._append(case_id, "memory.created", request_id, card=self._card_event_payload(card), created_by="script")
            updated = self._advance(case, expected_version, script_id=script_id, status="ready")
            self._append(case_id, "script.loaded", request_id, script_id=script_id, version=updated.version, card_ids=[card.id for card in cards])
            return self.snapshot(case_id)

    def reset_case(self, case_id: str, expected_version: int, request_id: str | None = None) -> CaseSnapshot:
        """Erase this case's scoped memory and return it to the empty-game state."""
        with self._command_lock:
            case = self.repository.get_case(case_id)
            self._require_version(case, expected_version)
            for agent_id in (*ROLE_IDS, AgentId.BULLETIN_BOARD):
                for card in self.gateway.list_space(case_id, agent_id):
                    self.gateway.delete_card(case_id, card)
            updated = case.model_copy(update={"version": case.version + 1, "script_id": None, "status": "empty"})
            self.repository.update_case(updated, expected_version)
            self._last_answers.pop(case_id, None)
            for key in [key for key in self._whisper_timestamps if key[0] == case_id]:
                self._whisper_timestamps.pop(key, None)
            resolved_request_id = self._request_id(request_id)
            self._append(case_id, "case.reset", resolved_request_id, version=updated.version, status=updated.status)
            return self.snapshot(case_id)

    def whisper(self, case_id: str, agent_id: AgentId, text: str, expected_version: int, request_id: str | None = None) -> tuple[MemoryCard, CaseSnapshot]:
        if not self.settings.demo_allow_freeform_whisper:
            raise FreeformDisabledError("freeform whispers are disabled")
        if agent_id not in ROLE_IDS:
            raise AccessViolationError("only roles have private memory spaces")
        with self._command_lock:
            self._validate_demo_whisper(text)
            self._consume_whisper_quota(case_id, agent_id)
            case = self.repository.get_case(case_id)
            self._require_version(case, expected_version)
            request_id = self._request_id(request_id)
            card = self.gateway.write_private(case_id, agent_id, text, topic="operator_whisper", kind="evidence", created_by="operator")
            updated = self._advance(case, expected_version)
            self._append(case_id, "memory.created", request_id, card=self._card_event_payload(card), created_by="operator", version=updated.version)
            return card, self.snapshot(case_id)

    def _validate_demo_whisper(self, text: str) -> None:
        """Keep the audience input fictional and avoid accepting obvious PII.

        The rejected value is deliberately not placed in exceptions, events, or
        logs. Operators can extend the baseline terms only through ``.env``.
        """
        compact = re.sub(r"[\s-]+", "", text)
        phone = re.compile(r"(?<!\d)(?:\+?86)?1[3-9]\d{9}(?!\d)")
        mainland_id = re.compile(r"(?<!\d)\d{17}[\dXx](?![\dA-Za-z])")
        if phone.search(compact) or mainland_id.search(compact):
            raise UnsafeWhisperError("freeform demo input cannot contain personal contact or identity numbers")
        if any(term.casefold() in text.casefold() for term in self.settings.disallowed_whisper_terms):
            raise UnsafeWhisperError("freeform demo input contains a disallowed sensitive-data term")

    def _consume_whisper_quota(self, case_id: str, agent_id: AgentId) -> None:
        limit = self.settings.demo_whisper_rate_limit_per_minute
        if limit == 0:
            return
        now = time.monotonic()
        key = (case_id, agent_id)
        current = [timestamp for timestamp in self._whisper_timestamps.get(key, []) if now - timestamp < 60]
        if len(current) >= limit:
            raise WhisperRateLimitError("freeform whisper rate limit exceeded")
        current.append(now)
        self._whisper_timestamps[key] = current

    def ask(self, case_id: str, agent_id: AgentId, question: str, expected_version: int, request_id: str | None = None) -> AnswerView:
        if agent_id not in ROLE_IDS:
            raise AccessViolationError("bulletin_board cannot be interrogated")
        case = self.repository.get_case(case_id)
        self._require_version(case, expected_version)
        request_id = self._request_id(request_id)
        started = time.perf_counter()
        private_cards = self.gateway.search_space(case_id, agent_id, question)
        public_cards = self.gateway.search_space(case_id, AgentId.BULLETIN_BOARD, question)
        # Preserve independent scopes but deduplicate a future re-published source.
        cards: list[MemoryCard] = []
        seen: set[str] = set()
        for card in [*private_cards, *public_cards]:
            if card.id not in seen:
                seen.add(card.id)
                cards.append(card)
        trace = RetrievalTrace(request_id=request_id, query=question, searched_scopes=[agent_id, AgentId.BULLETIN_BOARD], hit_cards=cards, duration_ms=round((time.perf_counter() - started) * 1000), mode=self.settings.demo_mode)
        self._append(
            case_id,
            "retrieval.completed",
            request_id,
            agent_id=agent_id.value,
            searched_scopes=[scope.value for scope in trace.searched_scopes],
            hit_card_ids=[card.id for card in cards],
            duration_ms=trace.duration_ms,
            mode=trace.mode,
        )
        result = self.answers.answer(agent_id, question, cards)
        answer = AnswerView(answer=result.answer, certainty=result.certainty, evidence_ids=result.evidence_ids, trace=trace, responder=result.responder, fallback_reason=result.fallback_reason)
        if result.fallback_reason:
            self._append(case_id, "agent.fallback", request_id, reason=result.fallback_reason)
        self._append(
            case_id,
            "answer.completed",
            request_id,
            certainty=answer.certainty.value,
            evidence_ids=answer.evidence_ids,
            responder=answer.responder,
            fallback_reason=answer.fallback_reason,
            trace_id=trace.request_id,
        )
        self._last_answers[case_id] = answer
        return answer

    def publish(self, case_id: str, source_agent_id: AgentId, memory_id: str, expected_version: int, request_id: str | None = None) -> tuple[MemoryCard, bool, CaseSnapshot]:
        if source_agent_id not in ROLE_IDS:
            raise AccessViolationError("only a private role card may be published")
        with self._command_lock:
            case = self.repository.get_case(case_id)
            existing = self.repository.find_publication(case_id, memory_id)
            if existing:
                existing_id = str(existing["public_card"]["card_id"])
                public = self.gateway.get_private(case_id, AgentId.BULLETIN_BOARD, existing_id)
                if public:
                    return public, True, self.snapshot(case_id)
            self._require_version(case, expected_version)
            source = self.gateway.get_private(case_id, source_agent_id, memory_id)
            if not source:
                # A card from another case fails here because every gateway request includes case:{id}.
                raise AccessViolationError("memory does not belong to this case and source role")
            if source.visibility.value != "private":
                raise AccessViolationError("only private source cards may be published")
            request_id = self._request_id(request_id)
            self._append(case_id, "memory.publishing", request_id, source_memory_id=source.id, source_agent_id=source_agent_id.value)
            public = self.gateway.write_public(case_id, source)
            updated = self._advance(case, expected_version)
            self._append(case_id, "memory.published", request_id, source_memory_id=source.id, source_agent_id=source_agent_id.value, public_card=self._card_event_payload(public), version=updated.version)
            return public, False, self.snapshot(case_id)

    def snapshot(self, case_id: str) -> CaseSnapshot:
        case = self.repository.get_case(case_id)
        spaces = {agent_id: self.gateway.list_space(case_id, agent_id) for agent_id in (*ROLE_IDS, AgentId.BULLETIN_BOARD)}
        latest_answer = self._last_answers.get(case_id)
        return CaseSnapshot(case=case, spaces=spaces, last_trace=latest_answer.trace if latest_answer else None, last_answer=latest_answer)

    @staticmethod
    def _public_card(card: MemoryCard) -> PublicMemoryCard:
        """Project a public replica without retaining a private source ID."""
        if card.owner_agent_id != AgentId.BULLETIN_BOARD or card.visibility.value != "public" or card.source_agent_id is None:
            raise AccessViolationError("only bulletin-board replicas may enter a display projection")
        return PublicMemoryCard(
            id=card.id,
            content=card.content,
            topic=card.topic,
            kind=card.kind,
            source_agent_id=card.source_agent_id,
            created_at=card.created_at,
        )

    def stage_snapshot(self, case_id: str) -> StageSnapshot:
        """Return the stage projection without serializing any private card."""
        snapshot = self.snapshot(case_id)
        latest_trace = snapshot.last_trace
        stage_trace = None
        if latest_trace:
            stage_trace = StageRetrievalView(
                searched_scopes=latest_trace.searched_scopes,
                public_hit_cards=[
                    self._public_card(card)
                    for card in latest_trace.hit_cards
                    if card.visibility.value == "public" and card.owner_agent_id == AgentId.BULLETIN_BOARD
                ],
                duration_ms=latest_trace.duration_ms,
            )
        return StageSnapshot(
            case=snapshot.case,
            private_memory_counts={agent_id: len(snapshot.spaces[agent_id]) for agent_id in ROLE_IDS},
            bulletin_board=[self._public_card(card) for card in snapshot.spaces[AgentId.BULLETIN_BOARD]],
            last_retrieval=stage_trace,
        )

    def public_snapshot(self, case_id: str) -> PublicSnapshot:
        """Return the smallest unauthenticated representation of a case."""
        snapshot = self.snapshot(case_id)
        return PublicSnapshot(
            case=snapshot.case,
            bulletin_board=[self._public_card(card) for card in snapshot.spaces[AgentId.BULLETIN_BOARD]],
        )

    def events_after(self, case_id: str, after_event_id: int) -> list[DomainEvent]:
        self.repository.get_case(case_id)
        return self.repository.events_after(case_id, after_event_id)

    def stage_events_after(self, case_id: str, after_event_id: int) -> list[StageEvent]:
        """Sanitize the event stream before it reaches a read-only display."""
        safe_events: list[StageEvent] = []
        for event in self.events_after(case_id, after_event_id):
            payload = event.payload
            safe_payload: dict[str, Any]
            if event.type in {"case.created", "case.reset"}:
                safe_payload = {key: payload[key] for key in ("version", "status") if key in payload}
            elif event.type == "script.loaded":
                safe_payload = {key: payload[key] for key in ("script_id", "version") if key in payload}
            elif event.type == "memory.created":
                # It reports activity, not the private card identifier or topic.
                safe_payload = {key: payload[key] for key in ("owner_agent_id", "visibility") if key in payload}
            elif event.type == "memory.published":
                public_card = payload.get("public_card")
                safe_payload = {"published": True}
                if isinstance(public_card, dict):
                    try:
                        # The stored event is a metadata-only card, so obtain the
                        # canonical public card from the current gateway instead.
                        public_id = public_card.get("card_id")
                        if isinstance(public_id, str):
                            card = self.gateway.get_private(case_id, AgentId.BULLETIN_BOARD, public_id)
                            if card:
                                safe_payload["public_card"] = self._public_card(card).model_dump(mode="json")
                    except (AccessViolationError, ValueError):
                        pass
            elif event.type in {"memory.publishing", "retrieval.completed", "answer.completed", "agent.fallback"}:
                safe_payload = {"completed": True}
            else:
                # New event types must opt in to a projection; an empty payload
                # preserves progress updates without leaking future fields.
                safe_payload = {}
            safe_events.append(StageEvent(
                event_id=event.event_id,
                type=event.type,
                created_at=event.created_at,
                payload=safe_payload,
            ))
        return safe_events

    def advanced_features(self) -> AdvancedFeaturesView:
        enabled = self.settings.demo_advanced_features_enabled
        return AdvancedFeaturesView(
            enabled=enabled,
            audit_timeline_enabled=enabled and self.settings.demo_audit_timeline_enabled,
            board_analysis_enabled=enabled and self.settings.demo_board_analysis_enabled,
            unsafe_fixture_enabled=self.settings.unsafe_fixture_is_available,
            native_share_experiment_enabled=enabled and self.settings.demo_native_share_experiment_enabled,
            freeform_whisper_enabled=self.settings.demo_allow_freeform_whisper,
            native_share_note="开发实验：AgentMemory share_memory 的持久化与撤销契约尚未全绿，主演示继续使用公告板复制。",
        )

    def audit_timeline(self, case_id: str) -> AuditTimeline:
        if not (self.settings.demo_advanced_features_enabled and self.settings.demo_audit_timeline_enabled):
            raise AdvancedFeatureDisabledError("the public audit timeline is disabled")
        self.repository.get_case(case_id)
        entries: list[AuditEntry] = []
        # Read only publication ledger events. Do not list or search any
        # private memory space merely to assemble a timeline.
        for event in self.repository.events_after(case_id, 0):
            if event.type != "memory.published":
                continue
            payload = event.payload
            source_agent_id = payload.get("source_agent_id")
            source_memory_id = payload.get("source_memory_id")
            public_card = payload.get("public_card")
            public_card_id = public_card.get("card_id") if isinstance(public_card, dict) else None
            if not isinstance(source_agent_id, str) or not isinstance(source_memory_id, str) or not isinstance(public_card_id, str):
                continue
            try:
                source_agent = AgentId(source_agent_id)
            except ValueError:
                continue
            entries.append(AuditEntry(
                event_id=event.event_id,
                created_at=event.created_at,
                operator="局长",
                source_agent_id=source_agent,
                source_memory_id=source_memory_id,
                public_card_id=public_card_id,
            ))
        return AuditTimeline(case_id=case_id, entries=entries)

    def analyze_public_board(self, case_id: str, query: str) -> BoardAnalysisView:
        if not (self.settings.demo_advanced_features_enabled and self.settings.demo_board_analysis_enabled):
            raise AdvancedFeatureDisabledError("public-material analysis is disabled")
        self.repository.get_case(case_id)
        # This is the only retrieval performed for the analysis request.  The
        # analyst receives its result, never a gateway, role space, or case id.
        cards = self.gateway.search_space(case_id, AgentId.BULLETIN_BOARD, query)
        return self.board_analyst.analyze(query, cards)

    def start_unsafe_fixture(self) -> UnsafeFixtureView:
        if not self.settings.unsafe_fixture_is_available:
            raise AdvancedFeatureDisabledError("unsafe fixture requires its flag on and freeform whispers off")
        return self.unsafe_fixture_lab.start()

    def close_unsafe_fixture(self, fixture_id: str) -> bool:
        if not self.settings.unsafe_fixture_is_available:
            raise AdvancedFeatureDisabledError("unsafe fixture is disabled")
        return self.unsafe_fixture_lab.close(fixture_id)

    def health(self) -> HealthView:
        memory_status, memory_detail = self.gateway.health()
        status = memory_status if memory_status in {"ok", "degraded", "unconfigured", "error"} else "error"
        llm = HealthPart(status="ok", detail=f"{self.settings.llm_provider}/{self.settings.llm_model}") if self.settings.llm_is_configured else HealthPart(status="degraded", detail="evidence mode is active; configure LLM_API_KEY and set DEMO_MODE=full for role phrasing")
        return HealthView(
            api=HealthPart(status="ok", detail="FastAPI is serving the game API"),
            powermem=HealthPart(status=status, detail=memory_detail),
            seekdb=HealthPart(status=status, detail=f"{self.settings.seekdb_mode} seekdb transport: {memory_detail}"),
            llm=llm,
            mode="full" if self.settings.llm_is_configured else "degrade",
        )

    def warmup(self) -> None:
        """Exercise the configured memory path before accepting a live audience."""
        case_id = f"warmup-{uuid.uuid4()}"
        card = self.gateway.write_private(case_id, AgentId.DETECTIVE, "warmup evidence 0427", topic="warmup", kind="evidence", created_by="warmup")
        hits = self.gateway.search_space(case_id, AgentId.DETECTIVE, "0427")
        if not any(hit.id == card.id for hit in hits):
            raise RuntimeError("memory warmup write/search contract failed")
        self.gateway.delete_card(case_id, card)

    def clear_ephemeral_data(self) -> None:
        """Delete every current case from PowerMem before erasing the local ledger."""
        with self._command_lock:
            for case_id in self.repository.case_ids():
                for agent_id in (*ROLE_IDS, AgentId.BULLETIN_BOARD):
                    for card in self.gateway.list_space(case_id, agent_id):
                        self.gateway.delete_card(case_id, card)
            self.repository.clear_all()
            self._last_answers.clear()
            self._whisper_timestamps.clear()

    def metrics(self) -> dict[str, int]:
        return self.repository.aggregate_metrics()
