"""Development-only AgentMemory native sharing adapter.

This adapter is purposely separate from the P1 ``MemoryGateway`` and its
copy-to-board semantics.  It is not constructed by ``build_gateway`` and is
therefore unable to change a live demo's publication path by configuration
accident or an incomplete AgentMemory experiment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class NativeShareReceipt:
    memory_id: str
    source_agent_id: str
    target_agent_ids: tuple[str, ...]
    success: bool


class NativeShareGateway:
    """Thin adapter around ``AgentMemory.share_memory`` for contract probes."""

    def __init__(self, agent_memory_factory: Callable[[], Any]) -> None:
        self._agent_memory_factory = agent_memory_factory

    def share(self, memory_id: str, source_agent_id: str, target_agent_ids: list[str]) -> NativeShareReceipt:
        if not memory_id or not source_agent_id or not target_agent_ids:
            raise ValueError("native share requires a memory, source role, and one target role")
        result = self._agent_memory_factory().share_memory(
            memory_id=memory_id,
            from_agent=source_agent_id,
            to_agents=target_agent_ids,
            permissions=["read"],
        )
        if not isinstance(result, dict) or not result.get("success"):
            raise RuntimeError("AgentMemory share_memory did not confirm a native share")
        shared_with = tuple(str(agent) for agent in result.get("shared_with", ()))
        if set(shared_with) != set(target_agent_ids):
            raise RuntimeError("AgentMemory share_memory did not grant every requested target")
        return NativeShareReceipt(str(memory_id), source_agent_id, shared_with, True)

    @staticmethod
    def contract_matrix() -> tuple[str, ...]:
        """The required P4 probe sequence; execution stays outside live demos."""
        return (
            "private write → native share → peer search",
            "restart → peer search",
            "revoke → peer search",
            "share again → peer search",
            "failure retry, duplicate share, and cross-case isolation",
        )
