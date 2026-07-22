from __future__ import annotations

from app.deepagents_probe import BLOCKED_TOOL_NAMES, run_probe


def test_deepagents_no_tools_probe_returns_structured_result():
    report = run_probe()

    assert report["deepagents_installed"]
    assert report["agent_invoked"]
    assert report["no_tools_boundary"]
    assert not set(report["visible_tool_names"]) & BLOCKED_TOOL_NAMES
    assert report["tool_calls"] == []
    assert report["structured_result"] == {
        "answer": "unknown",
        "certainty": "unknown",
        "evidence_ids": [],
    }
