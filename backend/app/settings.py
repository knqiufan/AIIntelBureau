"""集中式运行配置；不在业务代码中读取环境变量。"""

from __future__ import annotations

import hmac
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Demo 的全部可变运行参数。

    ``seekdb_mode=oceanbase`` 通过 PowerMem Python SDK 直接连接远端
    OceanBase / seekdb 的 MySQL 兼容端口；``embedded`` 则在当前进程
    启动嵌入式 seekdb。不会经过 PowerMem HTTP Server。
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    demo_env: Literal["development", "production"] = "development"
    demo_mode: Literal["full", "degrade"] = "degrade"
    demo_allow_freeform_whisper: bool = True
    demo_disallowed_whisper_terms: str = "身份证,手机号,银行卡号,真实住址"
    demo_whisper_rate_limit_per_minute: int = Field(default=6, ge=0, le=120)
    # Separate credentials create distinct server-side principals.  The old
    # DEMO_ACCESS_KEY is intentionally not accepted: one shared secret cannot
    # enforce a boundary between the operator and a read-only display.
    demo_operator_access_key: str = ""
    demo_stage_access_key: str = ""
    demo_access_cookie_secure: bool = False
    demo_trusted_https_proxy: bool = False
    demo_enable_smoke: bool = False
    demo_memory_adapter: Literal["production", "in_memory"] = "production"
    demo_warmup: bool = False
    demo_state_db_path: str = "./data/ai_intel_bureau_state.sqlite3"
    demo_data_retention: Literal["persistent", "ephemeral"] = "persistent"
    demo_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080"
    demo_log_level: str = "INFO"
    # P4 is intentionally feature-flagged. The audit projection is harmless
    # and on by default; the three experimental surfaces remain off until an
    # operator explicitly enables them in the deployment environment.
    demo_advanced_features_enabled: bool = True
    demo_audit_timeline_enabled: bool = True
    demo_board_analysis_enabled: bool = False
    demo_unsafe_fixture_enabled: bool = False
    demo_native_share_experiment_enabled: bool = False

    # seekdb / OceanBase direct connection. PowerMem SDK uses pyobvector's
    # mysql+oceanbase driver for this remote mode; no PowerMem HTTP service is
    # involved. Empty host explicitly selects the embedded branch below.
    seekdb_mode: Literal["oceanbase", "embedded"] = "oceanbase"
    seekdb_host: str = ""
    seekdb_port: int = Field(default=2881, ge=1, le=65535)
    seekdb_user: str = ""
    seekdb_password: str = ""
    seekdb_path: str = "./data/seekdb"
    seekdb_database: str = "ai_intel_bureau"
    seekdb_collection: str = "ai_intel_bureau_memories"
    seekdb_index_type: str = "HNSW"
    seekdb_metric: Literal["cosine", "l2", "inner_product"] = "cosine"
    seekdb_pool_recycle_seconds: int = Field(default=3600, ge=0, le=86400)
    seekdb_pool_pre_ping: bool = True

    # StepFun is OpenAI-protocol compatible; keys intentionally have no default.
    llm_provider: Literal["openai"] = "openai"
    llm_base_url: str = "https://api.stepfun.com/step_plan/v1"
    llm_api_key: str = ""
    llm_model: str = "step-3.7-flash"
    llm_temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    # Long-running hosted model calls are sometimes used during rehearsal;
    # keep the schema aligned with the checked-in 1800-second local profile.
    llm_timeout_seconds: float = Field(default=8.0, ge=1.0, le=1800.0)

    # Embeddings use the same OpenAI-compatible protocol and endpoint pattern.
    embedding_provider: Literal["openai", "siliconflow"] = "openai"
    embedding_base_url: str = "https://api.stepfun.com/step_plan/v1"
    embedding_api_key: str = ""
    embedding_model: str = "YOUR_EMBEDDING_MODEL"
    embedding_dimensions: int = Field(default=1024, ge=1)
    embedding_pass_dimensions: bool = True

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Reject an unsafe production configuration before the app starts."""
        if self.demo_env != "production":
            return self

        problems: list[str] = []
        operator_key = self.demo_operator_access_key.strip()
        stage_key = self.demo_stage_access_key.strip()
        if len(operator_key) < 16:
            problems.append("DEMO_OPERATOR_ACCESS_KEY must contain at least 16 characters")
        if len(stage_key) < 16:
            problems.append("DEMO_STAGE_ACCESS_KEY must contain at least 16 characters")
        if operator_key and hmac.compare_digest(operator_key, stage_key):
            problems.append("operator and stage access keys must be different")
        if not self.demo_access_cookie_secure:
            problems.append("DEMO_ACCESS_COOKIE_SECURE must be true")
        if not self.demo_trusted_https_proxy:
            problems.append("DEMO_TRUSTED_HTTPS_PROXY must be true")
        if not self.cors_origins or any(not origin.startswith("https://") for origin in self.cors_origins):
            problems.append("DEMO_CORS_ORIGINS must contain only explicit HTTPS origins")
        if self.demo_enable_smoke:
            problems.append("DEMO_ENABLE_SMOKE must remain false in production")
        if problems:
            raise ValueError("unsafe production configuration: " + "; ".join(problems))
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.demo_cors_origins.split(",") if item.strip()]

    @property
    def disallowed_whisper_terms(self) -> tuple[str, ...]:
        """Configured, display-safe terms that freeform demo content may not contain."""
        return tuple(item.strip() for item in self.demo_disallowed_whisper_terms.split(",") if item.strip())

    @property
    def llm_is_configured(self) -> bool:
        return self.demo_mode == "full" and bool(self.llm_api_key.strip())

    @property
    def unsafe_fixture_is_available(self) -> bool:
        """Unsafe teaching fixtures and audience freeform input never coexist."""
        return (
            self.demo_advanced_features_enabled
            and self.demo_unsafe_fixture_enabled
            and not self.demo_allow_freeform_whisper
        )

    @property
    def embedding_is_configured(self) -> bool:
        return bool(self.embedding_api_key.strip()) and not self.embedding_model.startswith("YOUR_")

    @property
    def memory_is_configured(self) -> bool:
        if self.seekdb_mode == "oceanbase":
            return (
                bool(self.seekdb_host.strip())
                and bool(self.seekdb_user.strip())
                and bool(self.seekdb_database.strip())
                and self.embedding_is_configured
            )
        return self.embedding_is_configured

    @property
    def seekdb_remote_is_configured(self) -> bool:
        """Whether the direct OceanBase/MySQL-compatible connection is usable."""
        return (
            bool(self.seekdb_host.strip())
            and bool(self.seekdb_user.strip())
            and bool(self.seekdb_database.strip())
        )

    def powermem_config(self) -> dict:
        """Return the direct PowerMem SDK configuration for either storage mode."""
        vector_store_config = {
            # Use PowerMem's top-level OceanBase fields.  Supplying only the
            # legacy connection_args object lets the provider config inject its
            # root@test/test defaults and override the intended remote account.
            # An empty host explicitly selects embedded seekdb.
            "host": self.seekdb_host.strip() if self.seekdb_mode == "oceanbase" else "",
            "port": str(self.seekdb_port),
            "user": self.seekdb_user,
            "password": self.seekdb_password,
            "db_name": self.seekdb_database,
            "ob_path": self.seekdb_path,
            "collection_name": self.seekdb_collection,
            "index_type": self.seekdb_index_type,
            "vidx_metric_type": self.seekdb_metric,
            "embedding_model_dims": self.embedding_dimensions,
            "pool_recycle": self.seekdb_pool_recycle_seconds,
            "pool_pre_ping": self.seekdb_pool_pre_ping,
        }
        embedder_config: dict[str, object] = {
            "api_key": self.embedding_api_key or None,
            "model": self.embedding_model,
        }
        if self.embedding_provider == "siliconflow":
            # SiliconFlow's native PowerMem provider expects this field. Its
            # vector output dimension still belongs to vector_store above.
            embedder_config["siliconflow_base_url"] = self.embedding_base_url
            if self.embedding_pass_dimensions:
                embedder_config["embedding_dims"] = self.embedding_dimensions
        else:
            # `openai` also works for SiliconFlow because its API is OpenAI
            # compatible. `pass_dimensions=false` is needed for fixed-size
            # models such as BAAI/bge-m3, which reject output-size overrides.
            embedder_config["openai_base_url"] = self.embedding_base_url
            embedder_config["embedding_dims"] = self.embedding_dimensions
            embedder_config["pass_dimensions"] = self.embedding_pass_dimensions
        return {
            "llm": {
                "provider": self.llm_provider,
                "config": {
                    "api_key": self.llm_api_key or None,
                    "model": self.llm_model,
                    "temperature": self.llm_temperature,
                    "openai_base_url": self.llm_base_url,
                },
            },
            "embedder": {
                "provider": self.embedding_provider,
                "config": embedder_config,
            },
            "vector_store": {
                "provider": "oceanbase",
                "config": vector_store_config,
            },
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
