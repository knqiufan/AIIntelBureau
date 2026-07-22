"""FastAPI composition and HTTP/SSE contract."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import re
import time
import uuid
from contextlib import asynccontextmanager
from enum import StrEnum
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse

from .domain import AdvancedFeaturesView, AgentId, AnswerView, AuditTimeline, BoardAnalysisRequest, BoardAnalysisView, CaseSnapshot, HealthView, InterrogationRequest, MetricsView, PublicationRequest, PublicationResponse, PublicSnapshot, ResetRequest, ScriptRequest, StageSnapshot, UnsafeFixtureView, WhisperRequest, WhisperResponse
from .memory import MemoryGateway, build_gateway
from .observability import RuntimeMetrics, configure_logging, request_id_context
from .repository import CaseNotFoundError, StateRepository, VersionConflictError
from .services import AccessViolationError, AdvancedFeatureDisabledError, BureauService, FreeformDisabledError, MemoryUnavailableError, UnsafeWhisperError, WhisperRateLimitError
from .settings import Settings, get_settings


class Principal(StrEnum):
    OPERATOR = "operator"
    STAGE = "stage"
    PUBLIC = "public"
    DEVELOPMENT = "development"


ACCESS_COOKIE_NAMES = {
    Principal.OPERATOR: "ai_intel_bureau_operator_session",
    Principal.STAGE: "ai_intel_bureau_stage_session",
}


def _access_cookie_value(access_key: str, principal: Principal) -> str:
    """A stable opaque session value scoped to one server-side principal."""
    message = f"ai-intel-bureau-session-v2:{principal.value}".encode("utf-8")
    return hmac.new(access_key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _principal_from_request(request: Request, settings: Settings) -> Principal:
    """Resolve credentials without treating a case ID as authorization."""
    supplied_key = request.headers.get("X-Demo-Access-Key", "")
    operator_key = settings.demo_operator_access_key.strip()
    stage_key = settings.demo_stage_access_key.strip()
    if operator_key and hmac.compare_digest(supplied_key, operator_key):
        return Principal.OPERATOR
    if stage_key and hmac.compare_digest(supplied_key, stage_key):
        return Principal.STAGE

    valid_operator_cookie = operator_key and hmac.compare_digest(
        request.cookies.get(ACCESS_COOKIE_NAMES[Principal.OPERATOR], ""),
        _access_cookie_value(operator_key, Principal.OPERATOR),
    )
    valid_stage_cookie = stage_key and hmac.compare_digest(
        request.cookies.get(ACCESS_COOKIE_NAMES[Principal.STAGE], ""),
        _access_cookie_value(stage_key, Principal.STAGE),
    )
    # A browser may hold both cookies after an operator tested the stage.  Keep
    # their roles separate by selecting the cookie appropriate to the route.
    if request.url.path.endswith("/stage-snapshot") or request.url.path.endswith("/stage-events"):
        if valid_stage_cookie:
            return Principal.STAGE
        if valid_operator_cookie:
            return Principal.OPERATOR
    if valid_operator_cookie:
        return Principal.OPERATOR
    if valid_stage_cookie:
        return Principal.STAGE
    if settings.demo_env == "development" and not operator_key and not stage_key:
        return Principal.DEVELOPMENT
    return Principal.PUBLIC


def _require_principal(request: Request, expected: Principal) -> None:
    actual = request.state.principal
    if actual == expected or actual == Principal.DEVELOPMENT:
        return
    if actual == Principal.PUBLIC:
        raise HTTPException(status_code=401, detail={"code": "ACCESS_KEY_REQUIRED", "message": "需要对应角色的访问口令。"})
    raise HTTPException(status_code=403, detail={"code": "ROLE_FORBIDDEN", "message": "当前会话无权访问此资源。"})


def create_app(settings: Settings | None = None, gateway: MemoryGateway | None = None, repository: StateRepository | None = None) -> FastAPI:
    settings = settings or get_settings()
    repository = repository or StateRepository(settings.demo_state_db_path)
    service = BureauService(settings, gateway or build_gateway(settings), repository)
    logger = configure_logging(settings.demo_log_level)
    runtime_metrics = RuntimeMetrics()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if settings.demo_data_retention == "ephemeral":
            service.clear_ephemeral_data()
        if settings.demo_warmup and settings.memory_is_configured:
            service.warmup()
        try:
            yield
        finally:
            if settings.demo_data_retention == "ephemeral":
                try:
                    service.clear_ephemeral_data()
                except Exception as exc:
                    logger.error("ephemeral.cleanup_failed", extra={"failure_type": type(exc).__name__})

    app = FastAPI(title="AI 情报局 API", version="0.1.0", lifespan=lifespan)
    app.state.service = service
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied if re.fullmatch(r"[A-Za-z0-9._-]{8,128}", supplied) else f"req_{uuid.uuid4().hex}"
        request.state.request_id = request_id
        request_token = request_id_context.set(request_id)
        started = time.perf_counter()
        try:
            request.state.principal = _principal_from_request(request, settings)
            response = await call_next(request)
        except Exception as exc:
            logger.error("http.request_failed", extra={"request_id": request_id, "path": request.url.path, "mode": settings.demo_mode, "failure_type": type(exc).__name__})
            raise
        finally:
            request_id_context.reset(request_token)
        response.headers["X-Request-ID"] = request_id
        runtime_metrics.record_response(response.status_code)
        logger.info("http.request_completed", extra={"request_id": request_id, "path": request.url.path, "status_code": response.status_code, "duration_ms": round((time.perf_counter() - started) * 1000), "mode": settings.demo_mode})
        return response

    @app.exception_handler(CaseNotFoundError)
    async def case_not_found(_: Request, exc: CaseNotFoundError):
        return _error(404, "CASE_NOT_FOUND", f"案件不存在：{exc.args[0]}")

    @app.exception_handler(VersionConflictError)
    async def version_conflict(_: Request, exc: VersionConflictError):
        latest = None
        try:
            latest = service.snapshot(exc.args[0]).model_dump(mode="json")
        except Exception:
            pass
        return _error(409, "VERSION_CONFLICT", "案件状态已变化，请使用最新快照重试。", latest_snapshot=latest)

    @app.exception_handler(AccessViolationError)
    async def forbidden(_: Request, exc: AccessViolationError):
        return _error(403, "VISIBILITY_BOUNDARY", str(exc))

    @app.exception_handler(FreeformDisabledError)
    async def freeform_disabled(_: Request, exc: FreeformDisabledError):
        return _error(403, "FREEFORM_DISABLED", str(exc))

    @app.exception_handler(UnsafeWhisperError)
    async def unsafe_whisper(_: Request, exc: UnsafeWhisperError):
        return _error(400, "UNSAFE_DEMO_INPUT", "仅可写入不含个人信息的虚构情报。")

    @app.exception_handler(WhisperRateLimitError)
    async def whisper_rate_limited(_: Request, exc: WhisperRateLimitError):
        return _error(429, "WHISPER_RATE_LIMIT", "该角色的自由耳语过于频繁，请稍后再试。")

    @app.exception_handler(MemoryUnavailableError)
    async def memory_unavailable(_: Request, exc: MemoryUnavailableError):
        return _error(503, "MEMORY_UNAVAILABLE", str(exc))

    @app.exception_handler(AdvancedFeatureDisabledError)
    async def advanced_feature_disabled(_: Request, exc: AdvancedFeatureDisabledError):
        return _error(403, "ADVANCED_FEATURE_DISABLED", "该高级能力未在当前部署中开启。", reason=str(exc))

    @app.get("/api/healthz", response_model=HealthView)
    def healthz():
        return service.health()

    @app.get("/api/readyz", response_model=HealthView)
    def readyz():
        health = service.health()
        if health.powermem.status != "ok":
            raise HTTPException(status_code=503, detail="memory storage is not ready")
        return health

    @app.post("/api/session", status_code=204)
    def establish_activity_session(request: Request):
        """Exchange one role-specific passcode for its HttpOnly session cookie."""
        principal: Principal = request.state.principal
        if principal not in {Principal.OPERATOR, Principal.STAGE}:
            return _error(401, "ACCESS_KEY_REQUIRED", "需要有效的局长或大屏访问口令。")
        response = Response(status_code=204)
        key = settings.demo_operator_access_key if principal == Principal.OPERATOR else settings.demo_stage_access_key
        response.set_cookie(
            ACCESS_COOKIE_NAMES[principal],
            _access_cookie_value(key, principal),
            httponly=True,
            secure=settings.demo_access_cookie_secure,
            samesite="lax",
            path="/",
        )
        return response

    @app.get("/api/advanced/status", response_model=AdvancedFeaturesView)
    def advanced_status(request: Request):
        _require_principal(request, Principal.OPERATOR)
        return service.advanced_features()

    @app.post("/api/advanced/unsafe-fixture", response_model=UnsafeFixtureView)
    def start_unsafe_fixture(request: Request):
        _require_principal(request, Principal.OPERATOR)
        return service.start_unsafe_fixture()

    @app.delete("/api/advanced/unsafe-fixture/{fixture_id}", status_code=204)
    def close_unsafe_fixture(fixture_id: str, request: Request):
        _require_principal(request, Principal.OPERATOR)
        # The fixture lives only in the process-local lab and has no storage
        # side effects. A missing id is already equivalent to a cleared case.
        service.close_unsafe_fixture(fixture_id)
        return Response(status_code=204)

    @app.post("/api/cases", response_model=CaseSnapshot)
    def create_case(request: Request):
        _require_principal(request, Principal.OPERATOR)
        return service.create_case(request.state.request_id)

    @app.post("/api/cases/{case_id}/script", response_model=CaseSnapshot)
    def load_script(case_id: str, body: ScriptRequest, request: Request):
        _require_principal(request, Principal.OPERATOR)
        return service.load_script(case_id, body.script_id, body.expected_version, request.state.request_id)

    @app.post("/api/cases/{case_id}/reset", response_model=CaseSnapshot)
    def reset_case(case_id: str, body: ResetRequest, request: Request):
        _require_principal(request, Principal.OPERATOR)
        return service.reset_case(case_id, body.expected_version, request.state.request_id)

    @app.post("/api/cases/{case_id}/whispers", response_model=WhisperResponse)
    def whisper(case_id: str, body: WhisperRequest, request: Request):
        _require_principal(request, Principal.OPERATOR)
        card, snapshot = service.whisper(case_id, body.agent_id, body.text, body.expected_version, request.state.request_id)
        return {"card": card, "snapshot": snapshot}

    @app.post("/api/cases/{case_id}/interrogations", response_model=AnswerView)
    def interrogate(case_id: str, body: InterrogationRequest, request: Request):
        _require_principal(request, Principal.OPERATOR)
        return service.ask(case_id, body.agent_id, body.question, body.expected_version, request.state.request_id)

    @app.post("/api/cases/{case_id}/publications", response_model=PublicationResponse)
    def publish(case_id: str, body: PublicationRequest, request: Request):
        _require_principal(request, Principal.OPERATOR)
        card, idempotent, snapshot = service.publish(case_id, body.source_agent_id, body.memory_id, body.expected_version, request.state.request_id)
        return {"card": card, "idempotent": idempotent, "snapshot": snapshot}

    @app.get("/api/cases/{case_id}/operator-snapshot", response_model=CaseSnapshot)
    def operator_snapshot(case_id: str, request: Request):
        _require_principal(request, Principal.OPERATOR)
        return service.snapshot(case_id)

    @app.get("/api/cases/{case_id}/stage-snapshot", response_model=StageSnapshot)
    def stage_snapshot(case_id: str, request: Request):
        _require_principal(request, Principal.STAGE)
        return service.stage_snapshot(case_id)

    @app.get("/api/cases/{case_id}/public-snapshot", response_model=PublicSnapshot)
    def public_snapshot(case_id: str):
        return service.public_snapshot(case_id)

    @app.get("/api/cases/{case_id}/audit", response_model=AuditTimeline)
    def audit_timeline(case_id: str, request: Request):
        _require_principal(request, Principal.OPERATOR)
        return service.audit_timeline(case_id)

    @app.post("/api/cases/{case_id}/board-analysis", response_model=BoardAnalysisView)
    def board_analysis(case_id: str, body: BoardAnalysisRequest, request: Request):
        _require_principal(request, Principal.OPERATOR)
        return service.analyze_public_board(case_id, body.query)

    @app.get("/api/metrics", response_model=MetricsView)
    def metrics(request: Request):
        _require_principal(request, Principal.OPERATOR)
        aggregate = service.metrics()
        aggregate.update(runtime_metrics.snapshot())
        aggregate["case_ready_rate_percent"] = round((aggregate["cases_ready"] / aggregate["cases_total"] * 100) if aggregate["cases_total"] else 0, 2)
        return aggregate

    @app.get("/api/cases/{case_id}/operator-events")
    async def operator_events(case_id: str, request: Request, after_event_id: int = 0):
        _require_principal(request, Principal.OPERATOR)
        service.snapshot(case_id)  # Validate before returning a long-lived connection.

        async def stream() -> AsyncIterator[str]:
            cursor = after_event_id
            while True:
                for event in service.events_after(case_id, cursor):
                    cursor = event.event_id
                    yield f"id: {event.event_id}\nevent: {event.type}\ndata: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/cases/{case_id}/stage-events")
    async def stage_events(case_id: str, request: Request, after_event_id: int = 0):
        _require_principal(request, Principal.STAGE)
        service.stage_snapshot(case_id)  # Validate before returning a long-lived connection.

        async def stream() -> AsyncIterator[str]:
            cursor = after_event_id
            while True:
                for event in service.stage_events_after(case_id, cursor):
                    cursor = event.event_id
                    yield f"id: {event.event_id}\nevent: {event.type}\ndata: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    if settings.demo_enable_smoke:
        @app.post("/api/_smoke/password-flow")
        def password_smoke(request: Request):
            _require_principal(request, Principal.OPERATOR)
            case = service.create_case().case
            loaded = service.load_script(case.case_id, "password", case.version)
            detective_before = service.ask(case.case_id, AgentId.DETECTIVE, "保险箱密码是多少？", loaded.case.version)
            informant = service.ask(case.case_id, AgentId.INFORMANT, "保险箱密码是多少？", loaded.case.version)
            source = next(card for card in loaded.spaces[AgentId.INFORMANT] if card.topic == "password")
            _, _, published = service.publish(case.case_id, AgentId.INFORMANT, source.id, loaded.case.version)
            detective_after = service.ask(case.case_id, AgentId.DETECTIVE, "保险箱密码是多少？", published.case.version)
            return {"case_id": case.case_id, "detective_before": detective_before, "informant": informant, "detective_after": detective_after}

    return app


def _error(status_code: int, code: str, message: str, **extra: object) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": {"code": code, "message": message, **extra}})


app = create_app()
