"""Offline proof that the pinned DeepAgents build can run a no-tools responder.

DeepAgents internally keeps a tool-node in its graph. The security boundary
that matters here is the tool set bound to the model: a role must receive an
empty tool list and return a structured response without a network, filesystem,
shell, task, or general-purpose subagent capability.
"""

from __future__ import annotations

import json
from typing import Any, Sequence

from pydantic import PrivateAttr


BLOCKED_TOOL_NAMES = frozenset({
    "write_todos",
    "ls",
    "read_file",
    "write_file",
    "edit_file",
    "delete",
    "glob",
    "grep",
    "execute",
    "task",
})


def run_probe() -> dict[str, Any]:
    """Build and invoke a fake, structured no-tools DeepAgents role locally."""
    try:
        from deepagents import HarnessProfile, create_deep_agent, register_harness_profile
        from deepagents.profiles import GeneralPurposeSubagentProfile
        from langchain_core.language_models.chat_models import BaseChatModel
        from langchain_core.messages import AIMessage, BaseMessage
        from langchain_core.outputs import ChatGeneration, ChatResult
    except ImportError as exc:
        return {"deepagents_installed": False, "failure": type(exc).__name__}

    class NoToolsProbeModel(BaseChatModel):
        """A deterministic local model that rejects any model-visible tools."""

        _bound_tool_sets: list[tuple[str, ...]] = PrivateAttr(default_factory=list)

        @property
        def _llm_type(self) -> str:
            return "ai_intel_bureau_no_tools_probe"

        @property
        def _identifying_params(self) -> dict[str, Any]:
            return {}

        def bind_tools(self, tools: Sequence[Any], *, tool_choice: Any = None, **_: Any) -> "NoToolsProbeModel":
            del tool_choice
            names = tuple(str(getattr(tool, "name", "unknown")) for tool in tools)
            self._bound_tool_sets.append(names)
            if names:
                raise AssertionError(f"tools must not be bound to the demo role: {names}")
            return self

        def _generate(
            self,
            messages: list[BaseMessage],
            stop: list[str] | None = None,
            run_manager: Any = None,
            **_: Any,
        ) -> ChatResult:
            del messages, stop, run_manager
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content='{"answer":"unknown","certainty":"unknown","evidence_ids":[]}'))])

    # The provider key is derived from this model class by DeepAgents.
    register_harness_profile(
        "notoolsprobemodel",
        HarnessProfile(
            excluded_tools=BLOCKED_TOOL_NAMES,
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        ),
    )
    model = NoToolsProbeModel()
    try:
        agent = create_deep_agent(model=model, tools=[])
        result = agent.invoke({"messages": [{"role": "user", "content": "Return the required evidence JSON."}]})
        last_message = result["messages"][-1]
        payload = json.loads(str(last_message.content))
        tool_calls = list(getattr(last_message, "tool_calls", []))
        visible_tools = [name for tool_set in model._bound_tool_sets for name in tool_set]
        return {
            "deepagents_installed": True,
            "agent_invoked": True,
            "visible_tool_names": visible_tools,
            "tool_calls": tool_calls,
            "structured_result": payload,
            "no_tools_boundary": not visible_tools and not tool_calls,
        }
    except Exception as exc:
        return {
            "deepagents_installed": True,
            "agent_invoked": False,
            "failure": type(exc).__name__,
        }
