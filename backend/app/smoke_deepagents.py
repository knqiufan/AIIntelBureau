"""P0 capability probe for the deliberately tool-less responder boundary."""

from __future__ import annotations

import json

from .deepagents_probe import run_probe


def main() -> int:
    report = run_probe()
    report["decision"] = (
        "the offline no-tools DeepAgents probe is pinned and tested; production role phrasing "
        "uses the same server-filtered evidence-only boundary when full mode is configured"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("deepagents_installed") and report.get("agent_invoked") and report.get("no_tools_boundary") else 1


if __name__ == "__main__":
    raise SystemExit(main())
