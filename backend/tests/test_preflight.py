from app.preflight import configuration_checks


def test_preflight_requires_direct_seekdb_configuration_and_full_mode_llm(settings):
    full = settings.model_copy(update={"demo_mode": "full"})
    checks = {check.name: check for check in configuration_checks(full)}

    assert not checks["seekdb_host"].ok
    assert checks["seekdb_host"].required
    assert not checks["seekdb_user"].ok
    assert not checks["role_llm"].ok
    assert checks["role_llm"].required


def test_preflight_accepts_complete_remote_full_configuration(settings):
    complete = settings.model_copy(update={
        "demo_mode": "full",
        "seekdb_host": "seekdb.example.test",
        "seekdb_user": "root@tenant#cluster",
        "seekdb_password": "configured-for-test-only",
        "llm_api_key": "configured-for-test-only",
            "embedding_api_key": "configured-for-test-only",
            "embedding_model": "embedding-test",
            "demo_external_data_egress_approved": True,
    })
    checks = configuration_checks(complete)

    assert all(check.ok for check in checks if check.required)


def test_preflight_requires_embedding_when_embedded_seekdb_is_selected(settings):
    embedded = settings.model_copy(update={"seekdb_mode": "embedded"})
    checks = {check.name: check for check in configuration_checks(embedded)}

    assert checks["embedded_seekdb_embedding"].required
    assert not checks["embedded_seekdb_embedding"].ok
