import asyncio
import pytest
from onto_platform.ingestion.llm_client import (
    LLMResponse, LLMToolCall, StubLiteLLM,
)
from onto_platform.ingestion.agent import (
    AgentRunResult, run_agent, StepCapExceeded, CancellationToken,
)
from onto_platform.ingestion.working_registry import WorkingRegistry

pytestmark = pytest.mark.asyncio


def _put_obj_call(rid: str, api_name: str) -> LLMToolCall:
    return LLMToolCall(
        id=f"c-{rid}",
        name="working_put_object_type",
        arguments={"definition": {
            "rid": rid, "api_name": api_name, "lifecycle_status": "ACTIVE",
        }},
        reason=f"interpret {rid} as ObjectType",
    )


async def test_agent_runs_through_to_final_message():
    stub = StubLiteLLM(responses=[
        LLMResponse(content=None, tool_calls=[
            _put_obj_call("ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "material"),
        ]),
        LLMResponse(content=None, tool_calls=[
            _put_obj_call("ri.obj.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "station"),
        ]),
        LLMResponse(content="done", tool_calls=[]),
    ])
    wr = WorkingRegistry.empty()
    result = await run_agent(
        wr, llm=stub, system_prompt="seed", user_prompt="add types",
        connection_ids=set(), max_steps=10, cancel=CancellationToken(),
    )
    assert isinstance(result, AgentRunResult)
    assert result.steps == 3
    assert "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" in wr.snapshot().object_types
    assert any("interpret" in d.reason for d in result.decisions)


async def test_agent_step_cap_raises():
    forever = LLMResponse(content=None, tool_calls=[
        _put_obj_call("ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "x"),
    ])
    stub = StubLiteLLM(responses=[forever, forever, forever, forever, forever])
    wr = WorkingRegistry.empty()
    with pytest.raises(StepCapExceeded):
        await run_agent(
            wr, llm=stub, system_prompt="", user_prompt="",
            connection_ids=set(), max_steps=2, cancel=CancellationToken(),
        )


async def test_agent_responds_to_cancellation():
    inf = LLMResponse(content=None, tool_calls=[
        _put_obj_call("ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "x"),
    ])
    stub = StubLiteLLM(responses=[inf] * 50)
    wr = WorkingRegistry.empty()
    cancel = CancellationToken()
    cancel.cancel()
    with pytest.raises(asyncio.CancelledError):
        await run_agent(
            wr, llm=stub, system_prompt="", user_prompt="",
            connection_ids=set(), max_steps=50, cancel=cancel,
        )
