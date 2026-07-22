"""Safely clear only demo-scoped PowerMem cards and the local state ledger."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from .domain import AgentId
from .memory import MemoryGateway, build_gateway
from .repository import StateRepository
from .services import BureauService
from .settings import Settings


@dataclass(frozen=True)
class ClearPlan:
    case_count: int
    remote_card_count: int | None
    remote_error: str | None


def inspect_clear_plan(repository: StateRepository, gateway: MemoryGateway) -> ClearPlan:
    """Read only the case-scoped records that this command may delete."""
    case_ids = repository.case_ids()
    try:
        remote_card_count = sum(
            len(gateway.list_space(case_id, agent_id))
            for case_id in case_ids
            for agent_id in AgentId
        )
    except Exception as exc:
        # Do not include endpoint details or credentials in a console transcript.
        return ClearPlan(len(case_ids), None, type(exc).__name__)
    return ClearPlan(len(case_ids), remote_card_count, None)


def main() -> int:
    parser = argparse.ArgumentParser(description="Clear only AI Intelligence Bureau demo data")
    parser.add_argument("--confirm", action="store_true", help="perform deletion; without it this is a dry run")
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="with --confirm, clear only the local SQLite ledger (leave remote memories untouched)",
    )
    args = parser.parse_args()

    settings = Settings()
    repository = StateRepository(settings.demo_state_db_path)
    gateway = build_gateway(settings)
    service = BureauService(settings, gateway, repository)
    plan = inspect_clear_plan(repository, gateway)

    if plan.remote_error:
        print(f"Local ledger contains {plan.case_count} case(s). Remote memory inspection is unavailable: {plan.remote_error}.")
    else:
        print(f"Scoped demo data: {plan.case_count} case(s), {plan.remote_card_count} PowerMem card(s).")

    if not args.confirm:
        print("Dry run only. Re-run with --confirm to clear both remote cards and the local ledger.")
        return 0

    if args.local_only:
        repository.clear_all()
        print("Local ledger cleared. Remote PowerMem/seekdb cards were intentionally retained.")
        return 0

    if plan.remote_error or not settings.memory_is_configured:
        print("Refusing deletion: configure a healthy memory transport first, or explicitly use --confirm --local-only.")
        return 2

    # Memory cards are deleted before the SQLite ledger. If remote deletion fails,
    # the ledger remains available for a safe retry instead of silently orphaning data.
    service.clear_ephemeral_data()
    print("Scoped remote PowerMem/seekdb cards and local demo ledger cleared.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
