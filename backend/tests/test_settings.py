import pytest
from pydantic import ValidationError

from app.settings import Settings


def test_default_configuration_is_direct_oceanbase_and_stepfun_openai_compatible():
    settings = Settings(_env_file=None)
    assert settings.seekdb_mode == "oceanbase"
    assert settings.llm_provider == "openai"
    assert settings.llm_model == "step-3.7-flash"
    assert settings.llm_base_url == "https://api.stepfun.com/step_plan/v1"
    assert settings.embedding_provider == "openai"
    assert settings.embedding_base_url == settings.llm_base_url


def test_production_configuration_fails_closed_without_role_keys_and_https_controls():
    with pytest.raises(ValidationError, match="unsafe production configuration"):
        Settings(_env_file=None, demo_env="production")


def test_production_configuration_accepts_distinct_role_keys_and_https_controls():
    settings = Settings(
        _env_file=None,
        demo_env="production",
        demo_operator_access_key="operator-access-key-12345",
        demo_stage_access_key="stage-access-key-678901",
        demo_access_cookie_secure=True,
        demo_trusted_https_proxy=True,
        demo_cors_origins="https://demo.example.test",
    )
    assert settings.demo_env == "production"
