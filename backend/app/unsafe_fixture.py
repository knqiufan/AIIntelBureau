"""Static, short-lived anti-pattern material for the P4 teaching screen.

It intentionally does not import the production memory gateway.  The named
``unsafe_global_search`` below demonstrates the anti-pattern using fictional
records only, so a live case can never accidentally invoke it.
"""

from __future__ import annotations

import uuid
from threading import RLock

from .domain import UnsafeFixtureView


_FIXTURE_ROWS = (
    {"agent_id": "informant", "content": "[隔离 fixture] 虚构的线人私密线索"},
    {"agent_id": "suspect", "content": "[隔离 fixture] 虚构的嫌疑人私密线索"},
)


def unsafe_global_search(_: str) -> list[dict[str, str]]:
    """The *wrong* shape: no agent_id constraint, fixture records only.

    This function is deliberately unavailable to the normal service and never
    receives a real card, a repository, or a memory gateway.
    """
    return [dict(row) for row in _FIXTURE_ROWS]


class UnsafeFixtureLab:
    def __init__(self) -> None:
        self._sessions: set[str] = set()
        self._lock = RLock()

    def start(self) -> UnsafeFixtureView:
        fixture_id = f"unsafe-{uuid.uuid4().hex}"
        with self._lock:
            self._sessions.add(fixture_id)
        return UnsafeFixtureView(
            fixture_id=fixture_id,
            case_id=f"fixture-{fixture_id}",
            tool_name="unsafe_global_search",
            warning="错误示例：省略 agent_id 会跨角色返回 fixture 里的虚构私密线索；它绝不连接真实案件。",
            result_count=len(unsafe_global_search("fixture")),
        )

    def close(self, fixture_id: str) -> bool:
        with self._lock:
            if fixture_id not in self._sessions:
                return False
            self._sessions.remove(fixture_id)
            return True
