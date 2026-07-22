"""P0 smoke probe: run against a real configured gateway or --in-memory."""

from __future__ import annotations

import argparse
import json

from .domain import AgentId
from .memory import InMemoryGateway, build_gateway
from .repository import StateRepository
from .services import BureauService
from .settings import Settings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in-memory", action="store_true", help="run deterministic CI probe without external services")
    args = parser.parse_args()
    settings = Settings(demo_state_db_path=":memory:", demo_mode="degrade")
    gateway = InMemoryGateway() if args.in_memory else build_gateway(settings)
    service = BureauService(settings, gateway, StateRepository(":memory:"))
    created = service.create_case().case
    loaded = service.load_script(created.case_id, "password", created.version)
    before = service.ask(created.case_id, AgentId.DETECTIVE, "保险箱密码是多少？", loaded.case.version)
    informant = service.ask(created.case_id, AgentId.INFORMANT, "保险箱密码是多少？", loaded.case.version)
    source = next(card for card in loaded.spaces[AgentId.INFORMANT] if card.topic == "password")
    _, _, after_publish = service.publish(created.case_id, AgentId.INFORMANT, source.id, loaded.case.version)
    after = service.ask(created.case_id, AgentId.DETECTIVE, "保险箱密码是多少？", after_publish.case.version)
    result = {
        "S2_agent_isolation": before.certainty.value == "unknown",
        "S3_case_isolation": not gateway.search_space("other-case", AgentId.INFORMANT, "密码"),
        "S4_board_copy": after.certainty.value == "known" and all(card.owner_agent_id == AgentId.BULLETIN_BOARD for card in after.trace.hit_cards),
        "informant_knows": informant.certainty.value == "known",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(result.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
