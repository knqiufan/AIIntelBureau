from __future__ import annotations

from fastapi.testclient import TestClient

from app.domain import AgentId
from app.main import create_app
from app.memory import InMemoryGateway
from app.repository import StateRepository
from app.settings import Settings


def test_api_contract_and_smoke_endpoint(settings):
    app = create_app(settings=settings, gateway=InMemoryGateway(), repository=StateRepository(settings.demo_state_db_path))
    client = TestClient(app)

    created = client.post("/api/cases").json()
    assert created["case"]["version"] == 0
    loaded = client.post(f"/api/cases/{created['case']['case_id']}/script", json={"script_id": "password", "expected_version": 0})
    assert loaded.status_code == 200
    answer = client.post(f"/api/cases/{created['case']['case_id']}/interrogations", json={"agent_id": "detective", "question": "保险箱密码是多少？", "expected_version": 1})
    assert answer.status_code == 200
    assert answer.json()["certainty"] == "unknown"
    assert client.get("/api/healthz").status_code == 200


def test_openapi_exposes_typed_game_responses(settings):
    app = create_app(settings=settings, gateway=InMemoryGateway(), repository=StateRepository(settings.demo_state_db_path))
    schema = TestClient(app).get("/openapi.json").json()

    responses = schema["paths"]
    assert responses["/api/cases"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/CaseSnapshot")
    assert responses["/api/cases/{case_id}/interrogations"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/AnswerView")
    assert responses["/api/cases/{case_id}/reset"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/CaseSnapshot")


def test_api_returns_latest_snapshot_on_conflict(settings):
    app = create_app(settings=settings, gateway=InMemoryGateway(), repository=StateRepository(settings.demo_state_db_path))
    client = TestClient(app)
    created = client.post("/api/cases").json()["case"]
    client.post(f"/api/cases/{created['case_id']}/script", json={"script_id": "password", "expected_version": 0})
    response = client.post(f"/api/cases/{created['case_id']}/whispers", json={"agent_id": "detective", "text": "过时写入", "expected_version": 0})
    assert response.status_code == 409


def test_request_id_metrics_and_event_payloads_are_privacy_safe(settings):
    repository = StateRepository(settings.demo_state_db_path)
    app = create_app(settings=settings, gateway=InMemoryGateway(), repository=repository)
    client = TestClient(app)
    create_id = "create-case-request-0001"
    created_response = client.post("/api/cases", headers={"X-Request-ID": create_id})
    assert created_response.headers["X-Request-ID"] == create_id
    case = created_response.json()["case"]
    loaded = client.post(
        f"/api/cases/{case['case_id']}/script",
        headers={"X-Request-ID": "load-script-request-0001"},
        json={"script_id": "password", "expected_version": case["version"]},
    ).json()
    private_text = "never-store-this-freeform-text-in-events"
    whispered = client.post(
        f"/api/cases/{case['case_id']}/whispers",
        headers={"X-Request-ID": "whisper-request-0001"},
        json={"agent_id": "detective", "text": private_text, "expected_version": loaded["case"]["version"]},
    ).json()
    interrogation_id = "interrogation-request-0001"
    answer = client.post(
        f"/api/cases/{case['case_id']}/interrogations",
        headers={"X-Request-ID": interrogation_id},
        json={"agent_id": "detective", "question": private_text, "expected_version": whispered["snapshot"]["case"]["version"]},
    ).json()

    assert answer["trace"]["request_id"] == interrogation_id
    events = repository.events_after(case["case_id"])
    assert all(private_text not in str(event.payload) for event in events)
    assert [event.request_id for event in events if event.type in {"retrieval.completed", "answer.completed"}] == [interrogation_id, interrogation_id]
    metrics = client.get("/api/metrics").json()
    assert metrics["answers_total"] == 1
    assert metrics["retrievals_total"] == 1
    assert metrics["http_requests_total"] >= 4
    assert metrics["case_ready_rate_percent"] == 100
    assert private_text not in str(metrics)


def test_ephemeral_retention_cleans_up_when_app_stops(settings):
    ephemeral = settings.model_copy(update={"demo_data_retention": "ephemeral"})
    repository = StateRepository(ephemeral.demo_state_db_path)
    gateway = InMemoryGateway()
    app = create_app(settings=ephemeral, gateway=gateway, repository=repository)

    with TestClient(app) as client:
        case = client.post("/api/cases").json()["case"]
        client.post(f"/api/cases/{case['case_id']}/script", json={"script_id": "password", "expected_version": case["version"]})
        assert repository.case_ids() == [case["case_id"]]

    assert repository.case_ids() == []
    assert gateway.list_space(case["case_id"], AgentId.INFORMANT) == []


def test_api_resets_a_case_with_optimistic_versioning(settings):
    app = create_app(settings=settings, gateway=InMemoryGateway(), repository=StateRepository(settings.demo_state_db_path))
    client = TestClient(app)
    created = client.post("/api/cases").json()["case"]
    loaded = client.post(f"/api/cases/{created['case_id']}/script", json={"script_id": "password", "expected_version": created["version"]}).json()
    reset = client.post(f"/api/cases/{created['case_id']}/reset", json={"expected_version": loaded["case"]["version"]})

    assert reset.status_code == 200
    assert reset.json()["case"]["status"] == "empty"
    assert reset.json()["case"]["script_id"] is None
    assert all(not cards for cards in reset.json()["spaces"].values())


def test_api_rejects_sensitive_freeform_input_without_echoing_it(settings):
    app = create_app(settings=settings, gateway=InMemoryGateway(), repository=StateRepository(settings.demo_state_db_path))
    client = TestClient(app)
    case = client.post("/api/cases").json()["case"]
    loaded = client.post(f"/api/cases/{case['case_id']}/script", json={"script_id": "password", "expected_version": case["version"]}).json()
    unsafe = "我的手机号是 13800138000"

    response = client.post(f"/api/cases/{case['case_id']}/whispers", json={"agent_id": "detective", "text": unsafe, "expected_version": loaded["case"]["version"]})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "UNSAFE_DEMO_INPUT"
    assert unsafe not in response.text


def test_api_returns_a_clean_rate_limit_response_for_freeform_input(settings):
    limited = settings.model_copy(update={"demo_whisper_rate_limit_per_minute": 1})
    app = create_app(settings=limited, gateway=InMemoryGateway(), repository=StateRepository(limited.demo_state_db_path))
    client = TestClient(app)
    case = client.post("/api/cases").json()["case"]
    loaded = client.post(f"/api/cases/{case['case_id']}/script", json={"script_id": "password", "expected_version": case["version"]}).json()
    first = client.post(f"/api/cases/{case['case_id']}/whispers", json={"agent_id": "detective", "text": "虚构耳语一", "expected_version": loaded["case"]["version"]})
    second = client.post(f"/api/cases/{case['case_id']}/whispers", json={"agent_id": "detective", "text": "虚构耳语二", "expected_version": first.json()["snapshot"]["case"]["version"]})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"]["code"] == "WHISPER_RATE_LIMIT"


def test_role_scoped_access_sessions_protect_game_routes_but_not_health(settings):
    protected = settings.model_copy(update={
        "demo_operator_access_key": "operator-passphrase-12345",
        "demo_stage_access_key": "stage-passphrase-67890123",
    })
    app = create_app(settings=protected, gateway=InMemoryGateway(), repository=StateRepository(protected.demo_state_db_path))
    client = TestClient(app)

    assert client.get("/api/healthz").status_code == 200
    denied = client.post("/api/cases")
    session = client.post("/api/session", headers={"X-Demo-Access-Key": "operator-passphrase-12345"})
    allowed = client.post("/api/cases")

    assert denied.status_code == 401
    assert denied.json()["detail"]["code"] == "ACCESS_KEY_REQUIRED"
    assert session.status_code == 204
    assert "operator-passphrase-12345" not in session.headers["set-cookie"]
    assert "ai_intel_bureau_operator_session" in session.headers["set-cookie"]
    assert allowed.status_code == 200


def test_operator_stage_and_public_projections_enforce_role_and_do_not_leak_private_cards(tmp_path):
    settings = Settings(
        _env_file=None,
        demo_env="production",
        demo_state_db_path=str(tmp_path / "state.sqlite3"),
        demo_operator_access_key="operator-passphrase-12345",
        demo_stage_access_key="stage-passphrase-67890123",
        demo_access_cookie_secure=True,
        demo_trusted_https_proxy=True,
        demo_cors_origins="https://demo.example.test",
    )
    app = create_app(settings=settings, gateway=InMemoryGateway(), repository=StateRepository(settings.demo_state_db_path))
    client = TestClient(app)
    operator_headers = {"X-Demo-Access-Key": settings.demo_operator_access_key}
    stage_headers = {"X-Demo-Access-Key": settings.demo_stage_access_key}

    first_case = client.post("/api/cases", headers=operator_headers).json()["case"]
    loaded = client.post(
        f"/api/cases/{first_case['case_id']}/script",
        headers=operator_headers,
        json={"script_id": "password", "expected_version": first_case["version"]},
    )
    assert loaded.status_code == 200
    second_case = client.post("/api/cases", headers=operator_headers).json()["case"]

    unauthenticated_operator = client.get(f"/api/cases/{first_case['case_id']}/operator-snapshot")
    unauthenticated_stage = client.get(f"/api/cases/{first_case['case_id']}/stage-snapshot")
    wrong_role_operator = client.get(f"/api/cases/{first_case['case_id']}/operator-snapshot", headers=stage_headers)
    wrong_role_stage = client.get(f"/api/cases/{first_case['case_id']}/stage-snapshot", headers=operator_headers)
    operator_snapshot = client.get(f"/api/cases/{first_case['case_id']}/operator-snapshot", headers=operator_headers)
    stage_snapshot = client.get(f"/api/cases/{first_case['case_id']}/stage-snapshot", headers=stage_headers)
    public_snapshot = client.get(f"/api/cases/{first_case['case_id']}/public-snapshot")
    other_case_stage = client.get(f"/api/cases/{second_case['case_id']}/stage-snapshot", headers=stage_headers)

    private_text = "保险箱密码是 0427"
    assert unauthenticated_operator.status_code == 401
    assert unauthenticated_stage.status_code == 401
    assert wrong_role_operator.status_code == 403
    assert wrong_role_stage.status_code == 403
    assert operator_snapshot.status_code == 200
    assert private_text in operator_snapshot.text
    assert stage_snapshot.status_code == 200
    assert private_text not in stage_snapshot.text
    assert "source_memory_id" not in stage_snapshot.text
    assert stage_snapshot.json()["private_memory_counts"]["informant"] == 1
    assert public_snapshot.status_code == 200
    assert private_text not in public_snapshot.text
    assert "private_memory_counts" not in public_snapshot.text
    assert other_case_stage.status_code == 200
    assert private_text not in other_case_stage.text

    stage_events = app.state.service.stage_events_after(first_case["case_id"], 0)
    serialized_events = "".join(event.model_dump_json() for event in stage_events)
    assert private_text not in serialized_events
    assert "source_memory_id" not in serialized_events
    assert "hit_card_ids" not in serialized_events


def test_smoke_route_is_not_registered_unless_explicitly_enabled(settings):
    app = create_app(settings=settings, gateway=InMemoryGateway(), repository=StateRepository(settings.demo_state_db_path))
    assert TestClient(app).post("/api/_smoke/password-flow").status_code == 404
