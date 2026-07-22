from app.settings import Settings


def test_default_configuration_is_direct_oceanbase_and_stepfun_openai_compatible():
    settings = Settings(_env_file=None)
    assert settings.seekdb_mode == "oceanbase"
    assert settings.llm_provider == "openai"
    assert settings.llm_model == "step-3.7-flash"
    assert settings.llm_base_url == "https://api.stepfun.com/step_plan/v1"
    assert settings.embedding_provider == "openai"
    assert settings.embedding_base_url == settings.llm_base_url
