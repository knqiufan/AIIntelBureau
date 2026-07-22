"""Credential-safe configuration checks for the operator before a live demo."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from .memory import build_gateway
from .settings import Settings


@dataclass(frozen=True)
class Check:
    name: str
    required: bool
    ok: bool
    detail: str


def configuration_checks(settings: Settings) -> list[Check]:
    checks: list[Check] = []
    if settings.seekdb_mode == "oceanbase":
        checks.append(Check("seekdb_host", True, bool(settings.seekdb_host.strip()), "configured" if settings.seekdb_host.strip() else "set SEEKDB_HOST to the OceanBase/seekdb host"))
        checks.append(Check("seekdb_user", True, bool(settings.seekdb_user.strip()), "configured" if settings.seekdb_user.strip() else "set SEEKDB_USER for the MySQL-compatible OceanBase connection"))
        checks.append(Check("seekdb_database", True, bool(settings.seekdb_database.strip()), "configured" if settings.seekdb_database.strip() else "set SEEKDB_DATABASE"))
        checks.append(Check("seekdb_password", False, bool(settings.seekdb_password.strip()), "configured" if settings.seekdb_password.strip() else "not set (valid only for passwordless database accounts)"))
    else:
        checks.append(Check("embedded_seekdb_embedding", True, settings.embedding_is_configured, "configured" if settings.embedding_is_configured else "set EMBEDDING_API_KEY and EMBEDDING_MODEL for embedded seekdb"))

    llm_required = settings.demo_mode == "full"
    checks.append(Check("role_llm", llm_required, bool(settings.llm_api_key.strip()), "configured" if settings.llm_api_key.strip() else ("set LLM_API_KEY because DEMO_MODE=full" if llm_required else "not required in degrade mode")))
    checks.append(Check("embedding", True, settings.embedding_is_configured, "configured" if settings.embedding_is_configured else "set EMBEDDING_API_KEY and EMBEDDING_MODEL"))
    protocol_ok = settings.embedding_provider in {"openai", "siliconflow"} and bool(settings.embedding_base_url.strip())
    checks.append(Check("embedding_protocol", False, protocol_ok, "OpenAI-compatible endpoint configured" if protocol_ok else "configure EMBEDDING_PROVIDER and EMBEDDING_BASE_URL"))
    checks.append(Check("activity_access_cookie", False, not settings.demo_access_key.strip() or settings.demo_access_cookie_secure, "not enabled or secure-cookie mode enabled" if not settings.demo_access_key.strip() or settings.demo_access_cookie_secure else "set DEMO_ACCESS_COOKIE_SECURE=true behind HTTPS"))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI Intelligence Bureau configuration without revealing secrets")
    parser.add_argument("--strict", action="store_true", help="exit non-zero when a required local configuration is absent")
    parser.add_argument("--check-remote", action="store_true", help="also initialize the direct PowerMem SDK connection (network request in oceanbase mode)")
    args = parser.parse_args()

    settings = Settings()
    checks = configuration_checks(settings)
    print(f"mode={settings.demo_mode}; seekdb_mode={settings.seekdb_mode}")
    for check in checks:
        marker = "OK" if check.ok else ("MISSING" if check.required else "NOTICE")
        print(f"[{marker}] {check.name}: {check.detail}")

    if args.check_remote:
        status, detail = build_gateway(settings).health()
        marker = "OK" if status == "ok" else "MISSING" if status == "unconfigured" else "ERROR"
        print(f"[{marker}] memory_connectivity: {status} ({detail})")
        if status != "ok":
            return 2

    if args.strict and any(check.required and not check.ok for check in checks):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
