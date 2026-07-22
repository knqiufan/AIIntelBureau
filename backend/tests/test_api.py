from __future__ import annotations

from fastapi.testclient import TestClient

from app.domain import AgentId
from app.main import create_app
from app.memory import InMemoryGateway
from app.repository import StateRepository


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


def test_optional_activity_access_key_protects_game_routes_but_not_health(settings):
    protected = settings.model_copy(update={"demo_access_key": "demo-passphrase"})
    app = create_app(settings=protected, gateway=InMemoryGateway(), repository=StateRepository(protected.demo_state_db_path))
    client = TestClient(app)

    assert client.get("/api/healthz").status_code == 200
    denied = client.post("/api/cases")
    session = client.post("/api/session", headers={"X-Demo-Access-Key": "demo-passphrase"})
    allowed = client.post("/api/cases")

    assert denied.status_code == 401
    assert denied.json()["detail"]["code"] == "ACCESS_KEY_REQUIRED"
    assert session.status_code == 204
    assert "demo-passphrase" not in session.headers["set-cookie"]
    assert allowed.status_code == 200
