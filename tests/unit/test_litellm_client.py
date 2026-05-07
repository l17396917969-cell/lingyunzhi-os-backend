from unittest.mock import AsyncMock, patch
import pytest
from onto_platform.ingestion.llm_client import LiteLLMClient

pytestmark = pytest.mark.asyncio


async def test_passes_through_to_litellm():
    fake_resp = type("R", (), {})()
    fake_resp.choices = [type("C", (), {"message": type("M", (), {
        "content": "hello",
        "tool_calls": None,
        "model_dump": lambda self: {"role": "assistant", "content": "hello"},
    })()})]
    with patch("litellm.acompletion", new=AsyncMock(return_value=fake_resp)) as mocked:
        c = LiteLLMClient(model="ark-code-latest", api_base="https://x", api_key="k")
        r = await c.acompletion(messages=[{"role": "user", "content": "hi"}], tools=[])
    assert r.content == "hello"
    assert r.tool_calls == []
    args = mocked.call_args.kwargs
    assert args["model"] == "ark-code-latest"
    assert args["api_base"] == "https://x"


async def test_parses_tool_calls():
    tc = type("TC", (), {})()
    tc.id = "call_1"
    tc.function = type("F", (), {"name": "put_object_type",
                                  "arguments": '{"definition": {}}'})()
    fake_resp = type("R", (), {})()
    fake_resp.choices = [type("C", (), {"message": type("M", (), {
        "content": None,
        "tool_calls": [tc],
        "model_dump": lambda self: {"role": "assistant", "content": None,
                                    "tool_calls": [{"id": "call_1"}]},
    })()})]
    with patch("litellm.acompletion", new=AsyncMock(return_value=fake_resp)):
        c = LiteLLMClient(model="m", api_base="u", api_key="k")
        r = await c.acompletion(messages=[], tools=[])
    assert len(r.tool_calls) == 1
    assert r.tool_calls[0].name == "put_object_type"
    assert r.tool_calls[0].arguments == {"definition": {}}
