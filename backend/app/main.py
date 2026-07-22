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
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse

from .domain import AdvancedFeaturesView, AgentId, AnswerView, AuditTimeline, BoardAnalysisRequest, BoardAnalysisView, CaseSnapshot, HealthView, InterrogationRequest, MetricsView, PublicationRequest, PublicationResponse, ResetRequest, ScriptRequest, UnsafeFixtureView, WhisperRequest, WhisperResponse
from .memory import MemoryGateway, build_gateway
from .observability import RuntimeMetrics, configure_logging, request_id_context
from .repository import CaseNotFoundError, StateRepository, VersionConflictError
from .services import AccessViolationError, AdvancedFeatureDisabledError, BureauService, FreeformDisabledError, MemoryUnavailableError, UnsafeWhisperError, WhisperRateLimitError
from .settings import Settings, get_settings


ACCESS_COOKIE_NAME = "ai_intel_bureau_access"


def _access_cookie_value(access_key: str) -> str:
    """A stable opaque session value; the original passcode never enters a URL."""
    return hmac.new(access_key.encode("utf-8"), b"ai-intel-bureau-session-v1", hashlib.sha256).hexdigest()


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
            protected = request.url.path.startswith("/api/") and request.url.path not in {"/api/healthz", "/api/readyz"}
            supplied_key = request.headers.get("X-Demo-Access-Key", "")
            supplied_cookie = request.cookies.get(ACCESS_COOKIE_NAME, "")
            valid_header = bool(settings.demo_access_key) and hmac.compare_digest(supplied_key, settings.demo_access_key)
            valid_cookie = bool(settings.demo_access_key) and hmac.compare_digest(supplied_cookie, _access_cookie_value(settings.demo_access_key))
            if settings.demo_access_key and protected and not (valid_header or valid_cookie):
                response = _error(401, "ACCESS_KEY_REQUIRED", "需要活动口令才能访问此演示。")
            else:
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
    def establish_activity_session():
        """The middleware has already checked the passcode header or cookie."""
        response = Response(status_code=204)
        if settings.demo_access_key:
            response.set_cookie(
                ACCESS_COOKIE_NAME,
                _access_cookie_value(settings.demo_access_key),
                httponly=True,
                secure=settings.demo_access_cookie_secure,
                samesite="lax",
                path="/",
            )
        return response

    @app.get("/api/advanced/status", response_model=AdvancedFeaturesView)
    def advanced_status():
        return service.advanced_features()

    @app.post("/api/advanced/unsafe-fixture", response_model=UnsafeFixtureView)
    def start_unsafe_fixture():
        return service.start_unsafe_fixture()

    @app.delete("/api/advanced/unsafe-fixture/{fixture_id}", status_code=204)
    def close_unsafe_fixture(fixture_id: str):
        # The fixture lives only in the process-local lab and has no storage
        # side effects. A missing id is already equivalent to a cleared case.
        service.close_unsafe_fixture(fixture_id)
        return Response(status_code=204)

    @app.post("/api/cases", response_model=CaseSnapshot)
    def create_case(request: Request):
        return service.create_case(request.state.request_id)

    @app.post("/api/cases/{case_id}/script", response_model=CaseSnapshot)
    def load_script(case_id: str, body: ScriptRequest, request: Request):
        return service.load_script(case_id, body.script_id, body.expected_version, request.state.request_id)

    @app.post("/api/cases/{case_id}/reset", response_model=CaseSnapshot)
    def reset_case(case_id: str, body: ResetRequest, request: Request):
        return service.reset_case(case_id, body.expected_version, request.state.request_id)

    @app.post("/api/cases/{case_id}/whispers", response_model=WhisperResponse)
    def whisper(case_id: str, body: WhisperRequest, request: Request):
        card, snapshot = service.whisper(case_id, body.agent_id, body.text, body.expected_version, request.state.request_id)
        return {"card": card, "snapshot": snapshot}

    @app.post("/api/cases/{case_id}/interrogations", response_model=AnswerView)
    def interrogate(case_id: str, body: InterrogationRequest, request: Request):
        return service.ask(case_id, body.agent_id, body.question, body.expected_version, request.state.request_id)

    @app.post("/api/cases/{case_id}/publications", response_model=PublicationResponse)
    def publish(case_id: str, body: PublicationRequest, request: Request):
        card, idempotent, snapshot = service.publish(case_id, body.source_agent_id, body.memory_id, body.expected_version, request.state.request_id)
        return {"card": card, "idempotent": idempotent, "snapshot": snapshot}

    @app.get("/api/cases/{case_id}/snapshot", response_model=CaseSnapshot)
    def snapshot(case_id: str):
        return service.snapshot(case_id)

    @app.get("/api/cases/{case_id}/audit", response_model=AuditTimeline)
    def audit_timeline(case_id: str):
        return service.audit_timeline(case_id)

    @app.post("/api/cases/{case_id}/board-analysis", response_model=BoardAnalysisView)
    def board_analysis(case_id: str, body: BoardAnalysisRequest):
        return service.analyze_public_board(case_id, body.query)

    @app.get("/api/metrics", response_model=MetricsView)
    def metrics():
        aggregate = service.metrics()
        aggregate.update(runtime_metrics.snapshot())
        aggregate["case_ready_rate_percent"] = round((aggregate["cases_ready"] / aggregate["cases_total"] * 100) if aggregate["cases_total"] else 0, 2)
        return aggregate

    @app.get("/api/cases/{case_id}/events")
    async def events(case_id: str, after_event_id: int = 0):
        service.snapshot(case_id)  # Validate before returning a long-lived connection.

        async def stream() -> AsyncIterator[str]:
            cursor = after_event_id
            while True:
                for event in service.events_after(case_id, cursor):
                    cursor = event.event_id
                    yield f"id: {event.event_id}\nevent: {event.type}\ndata: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/_smoke/password-flow")
    def password_smoke():
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
