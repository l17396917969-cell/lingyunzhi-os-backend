from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from onto_platform.ingestion.llm_client import LLMClient
from onto_platform.ingestion.tools import AGENT_TOOLS, AgentToolError, dispatch_agent_call
from onto_platform.ingestion.working_registry import WorkingRegistry


class StepCapExceeded(Exception):
    pass


class CancellationToken:
    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled


@dataclass
class AgentDecision:
    tool: str
    args_summary: dict[str, Any]
    outcome: str
    reason: str = ""
    error: str = ""


@dataclass
class AgentRunResult:
    final_message: str
    steps: int
    decisions: list[AgentDecision] = field(default_factory=list)


def _summarize_args(args: dict[str, Any]) -> dict[str, Any]:
    """Compact args for the report: keep RIDs/modes/api_names; trim large structures."""
    out: dict[str, Any] = {}
    for k, v in args.items():
        if k == "definition" and isinstance(v, dict):
            out[k] = {kk: v.get(kk) for kk in ("rid", "api_name", "lifecycle_status") if kk in v}
        elif k == "registry" and isinstance(v, dict):
            out[k] = {
                "entity_counts": {
                    kk: len(v.get(kk, {}))
                    for kk in (
                        "shared_property_types",
                        "interface_types",
                        "object_types",
                        "link_types",
                        "action_types",
                    )
                }
            }
        elif k == "asset_mapping" and isinstance(v, dict):
            out[k] = {
                kk: v.get(kk)
                for kk in ("read_connection_id", "read_asset_path")
                if kk in v
            }
        else:
            out[k] = v
    return out


async def run_agent(
    wr: WorkingRegistry,
    *,
    llm: LLMClient,
    system_prompt: str,
    user_prompt: str,
    connection_ids: set[str],
    max_steps: int,
    cancel: CancellationToken,
) -> AgentRunResult:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    decisions: list[AgentDecision] = []

    for step in range(1, max_steps + 1):
        if cancel.cancelled:
            raise asyncio.CancelledError("agent cancelled before step")

        resp = await llm.acompletion(messages=messages, tools=AGENT_TOOLS, tool_choice="auto")

        # Build the assistant turn explicitly (decoupled from LiteLLM internals)
        tool_calls_serialized: list[dict[str, Any]] | None = (
            [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in resp.tool_calls
            ]
            if resp.tool_calls
            else None
        )
        messages.append(
            {
                "role": "assistant",
                "content": resp.content,
                "tool_calls": tool_calls_serialized,
            }
        )

        if not resp.tool_calls:
            return AgentRunResult(
                final_message=resp.content or "",
                steps=step,
                decisions=decisions,
            )

        for call in resp.tool_calls:
            if cancel.cancelled:
                raise asyncio.CancelledError("agent cancelled mid-step")
            try:
                tool_result = dispatch_agent_call(
                    wr, call.name, call.arguments, connection_ids=connection_ids
                )
                decisions.append(
                    AgentDecision(
                        tool=call.name,
                        args_summary=_summarize_args(call.arguments),
                        outcome="ok",
                        reason=call.reason or "",
                    )
                )
                tool_content = json.dumps(tool_result)
            except AgentToolError as e:
                decisions.append(
                    AgentDecision(
                        tool=call.name,
                        args_summary=_summarize_args(call.arguments),
                        outcome="unknown_tool",
                        reason=call.reason or "",
                        error=str(e),
                    )
                )
                tool_content = json.dumps({"error": "unknown_tool", "message": str(e)})
            except Exception as e:
                decisions.append(
                    AgentDecision(
                        tool=call.name,
                        args_summary=_summarize_args(call.arguments),
                        outcome="error",
                        reason=call.reason or "",
                        error=str(e),
                    )
                )
                tool_content = json.dumps({"error": type(e).__name__, "message": str(e)})
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": tool_content}
            )

    raise StepCapExceeded(f"agent exceeded max_steps={max_steps}")
