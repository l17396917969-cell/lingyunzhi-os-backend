import pytest
from onto_platform.ingestion.llm_client import (
    LLMResponse, LLMToolCall, StubLiteLLM, StubExhaustedError,
)

pytestmark = pytest.mark.asyncio


async def test_stub_returns_scripted_responses():
    stub = StubLiteLLM(responses=[
        LLMResponse(content=None, tool_calls=[
            LLMToolCall(id="c1", name="working_put_object_type", arguments={"definition": {}}, reason="seed"),
        ]),
        LLMResponse(content="done", tool_calls=[]),
    ])
    r1 = await stub.acompletion(messages=[], tools=[])
    assert r1.tool_calls[0].name == "working_put_object_type"
    r2 = await stub.acompletion(messages=[], tools=[])
    assert r2.content == "done"


async def test_stub_records_calls():
    stub = StubLiteLLM(responses=[LLMResponse(content="ok", tool_calls=[])])
    await stub.acompletion(messages=[{"role": "user", "content": "hi"}], tools=[{"name": "x"}])
    assert len(stub.calls) == 1
    assert stub.calls[0].messages[0]["content"] == "hi"


async def test_stub_raises_when_exhausted():
    stub = StubLiteLLM(responses=[LLMResponse(content="ok", tool_calls=[])])
    await stub.acompletion(messages=[], tools=[])
    with pytest.raises(StubExhaustedError):
        await stub.acompletion(messages=[], tools=[])
