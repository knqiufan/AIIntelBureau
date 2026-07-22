"""Typed domain and API models shared by all backend layers."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class AgentId(str, Enum):
    DETECTIVE = "detective"
    INFORMANT = "informant"
    SUSPECT = "suspect"
    BULLETIN_BOARD = "bulletin_board"


class CaseMode(str, Enum):
    """Runtime operating mode exposed to clients and retained in traces."""

    FULL = "full"
    DEGRADE = "degrade"


ROLE_IDS: tuple[AgentId, ...] = (
    AgentId.DETECTIVE,
    AgentId.INFORMANT,
    AgentId.SUSPECT,
)


class MemoryVisibility(str, Enum):
    PRIVATE = "private"
    PUBLIC = "public"


class Certainty(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"


class MemoryCard(BaseModel):
    """Only display-safe memory fields may cross the API boundary."""

    model_config = ConfigDict(frozen=True)

    id: str
    content: str
    owner_agent_id: AgentId
    visibility: MemoryVisibility
    topic: str = "general"
    kind: str = "evidence"
    score: float | None = None
    source_agent_id: AgentId | None = None
    source_memory_id: str | None = None
    created_at: datetime = Field(default_factory=now_utc)

    @model_validator(mode="after")
    def validate_provenance(self) -> "MemoryCard":
        if self.visibility == MemoryVisibility.PRIVATE and self.owner_agent_id == AgentId.BULLETIN_BOARD:
            raise ValueError("private memory cannot be owned by bulletin_board")
        if self.visibility == MemoryVisibility.PUBLIC:
            if self.owner_agent_id != AgentId.BULLETIN_BOARD:
                raise ValueError("public memory must be owned by bulletin_board")
            if not self.source_agent_id or not self.source_memory_id:
                raise ValueError("public memory requires source provenance")
        return self


class RetrievalTrace(BaseModel):
    request_id: str
    query: str
    searched_scopes: list[AgentId]
    hit_cards: list[MemoryCard]
    duration_ms: int = Field(ge=0)
    mode: CaseMode


class AnswerView(BaseModel):
    answer: str
    certainty: Certainty
    evidence_ids: list[str]
    trace: RetrievalTrace
    responder: Literal["deterministic", "deepagents"]
    fallback_reason: str | None = None

    @model_validator(mode="after")
    def answer_is_grounded(self) -> "AnswerView":
        available = {card.id for card in self.trace.hit_cards}
        if not set(self.evidence_ids).issubset(available):
            raise ValueError("answer cited a memory outside its evidence packet")
        if not self.trace.hit_cards and self.certainty != Certainty.UNKNOWN:
            raise ValueError("an empty evidence packet must produce unknown")
        return self


class CaseState(BaseModel):
    case_id: str
    script_id: str | None = None
    version: int = 0
    status: Literal["empty", "ready"] = "empty"
    created_at: datetime = Field(default_factory=now_utc)


class CaseSnapshot(BaseModel):
    case: CaseState
    spaces: dict[AgentId, list[MemoryCard]]
    last_trace: RetrievalTrace | None = None
    last_answer: AnswerView | None = None


class WhisperResponse(BaseModel):
    card: MemoryCard
    snapshot: CaseSnapshot


class PublicationResponse(BaseModel):
    card: MemoryCard
    idempotent: bool
    snapshot: CaseSnapshot


class DomainEvent(BaseModel):
    event_id: int
    case_id: str
    type: str
    request_id: str
    payload: dict[str, Any]
    created_at: datetime = Field(default_factory=now_utc)


class ScriptRequest(BaseModel):
    script_id: Literal["password", "mole", "allergy"]
    expected_version: int = Field(ge=0)


class ResetRequest(BaseModel):
    expected_version: int = Field(ge=0)


class WhisperRequest(BaseModel):
    agent_id: AgentId
    text: str = Field(min_length=1, max_length=50)
    expected_version: int = Field(ge=0)

    @field_validator("agent_id")
    @classmethod
    def no_board_whispers(cls, value: AgentId) -> AgentId:
        if value == AgentId.BULLETIN_BOARD:
            raise ValueError("cannot whisper to bulletin_board")
        return value


class InterrogationRequest(BaseModel):
    agent_id: AgentId
    question: str = Field(min_length=1, max_length=300)
    expected_version: int = Field(ge=0)

    @field_validator("agent_id")
    @classmethod
    def only_roles_are_interrogable(cls, value: AgentId) -> AgentId:
        if value == AgentId.BULLETIN_BOARD:
            raise ValueError("bulletin_board is not a chat role")
        return value


class PublicationRequest(BaseModel):
    source_agent_id: AgentId
    memory_id: str
    expected_version: int = Field(ge=0)

    @field_validator("source_agent_id")
    @classmethod
    def no_board_republication(cls, value: AgentId) -> AgentId:
        if value == AgentId.BULLETIN_BOARD:
            raise ValueError("bulletin_board cards cannot be published again")
        return value


class HealthPart(BaseModel):
    status: Literal["ok", "degraded", "unconfigured", "error"]
    detail: str


class HealthView(BaseModel):
    api: HealthPart
    powermem: HealthPart
    seekdb: HealthPart
    llm: HealthPart
    mode: CaseMode


class AdvancedFeaturesView(BaseModel):
    """Feature flags deliberately exposed to the operator UI.

    The flags describe availability only. They never grant a client a broader
    memory scope: every advanced route enforces the same setting server-side.
    """

    enabled: bool
    audit_timeline_enabled: bool
    board_analysis_enabled: bool
    unsafe_fixture_enabled: bool
    native_share_experiment_enabled: bool
    freeform_whisper_enabled: bool
    native_share_note: str


class AuditEntry(BaseModel):
    """A read-only, publication-only projection of the event ledger."""

    event_id: int
    created_at: datetime
    operator: str
    source_agent_id: AgentId
    source_memory_id: str
    public_card_id: str


class AuditTimeline(BaseModel):
    case_id: str
    entries: list[AuditEntry]


class PublicFact(BaseModel):
    """A fact is always traceable to one public bulletin-board card."""

    card_id: str
    statement: str
    topic: str
    source_agent_id: AgentId


class AnalysisRisk(BaseModel):
    severity: Literal["low", "medium", "high"]
    title: str
    detail: str
    related_card_ids: list[str] = Field(default_factory=list)


class BoardAnalysisRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)


class BoardAnalysisView(BaseModel):
    query: str
    facts: list[PublicFact]
    risks: list[AnalysisRisk]
    responder: Literal["deterministic", "deepagents"]
    notice: str = "辅助分析，不改变角色可见记忆。"


class UnsafeFixtureView(BaseModel):
    """A static, isolated anti-pattern fixture; it is not a live case."""

    fixture_id: str
    case_id: str
    tool_name: Literal["unsafe_global_search"]
    warning: str
    result_count: int


class MetricsView(BaseModel):
    cases_total: int = Field(ge=0)
    cases_ready: int = Field(ge=0)
    events_total: int = Field(ge=0)
    publications_total: int = Field(ge=0)
    answers_total: int = Field(ge=0)
    fallbacks_total: int = Field(ge=0)
    retrievals_total: int = Field(ge=0)
    retrieval_duration_ms_total: int = Field(ge=0)
    http_requests_total: int = Field(ge=0)
    http_errors_total: int = Field(ge=0)
    http_errors_by_status: dict[str, int]
    case_ready_rate_percent: float = Field(ge=0, le=100)
