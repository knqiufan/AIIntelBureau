"""P3 repetition rehearsal: exercise the four-screen script N times."""

from __future__ import annotations

import argparse
import json

from .domain import AgentId
from .memory import InMemoryGateway, build_gateway
from .repository import StateRepository
from .services import BureauService
from .settings import Settings


def run_once(service: BureauService) -> bool:
    created = service.create_case().case
    loaded = service.load_script(created.case_id, "password", created.version)
    before = service.ask(created.case_id, AgentId.DETECTIVE, "保险箱密码是多少？", loaded.case.version)
    source = next(card for card in loaded.spaces[AgentId.INFORMANT] if card.topic == "password")
    _, _, published = service.publish(created.case_id, AgentId.INFORMANT, source.id, loaded.case.version)
    after = service.ask(created.case_id, AgentId.DETECTIVE, "保险箱密码是多少？", published.case.version)
    return before.certainty.value == "unknown" and after.certainty.value == "known" and all(card.owner_agent_id == AgentId.BULLETIN_BOARD for card in after.trace.hit_cards)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--in-memory", action="store_true")
    args = parser.parse_args()
    settings = Settings(demo_state_db_path=":memory:", demo_mode="degrade")
    gateway = InMemoryGateway() if args.in_memory else build_gateway(settings)
    service = BureauService(settings, gateway, StateRepository(":memory:"))
    passed = sum(run_once(service) for _ in range(args.runs))
    print(json.dumps({"runs": args.runs, "passed": passed, "failed": args.runs - passed}, ensure_ascii=False))
    return 0 if passed == args.runs else 1


if __name__ == "__main__":
    raise SystemExit(main())
