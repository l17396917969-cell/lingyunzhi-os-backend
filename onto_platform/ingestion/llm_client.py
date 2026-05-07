from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


@dataclass
class LLMToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    reason: Optional[str] = None  # the model's stated rationale (free-text)


@dataclass
class LLMResponse:
    content: Optional[str]
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    raw: Any = None


class LLMClient(Protocol):
    async def acompletion(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: str = "auto",
    ) -> LLMResponse: ...


class StubExhaustedError(RuntimeError):
    """Raised by StubLiteLLM when all scripted responses have been consumed.

    Named StubExhaustedError rather than StopIteration because PEP 479 converts
    any StopIteration raised inside a coroutine into RuntimeError, making the
    original exception un-catchable by callers.  StubExhaustedError is a
    RuntimeError subclass that callers can catch directly.
    """


@dataclass
class _StubCallRecord:
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]


class StubLiteLLM:
    """Test double.  Yields responses in order; raises StubExhaustedError when exhausted."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[_StubCallRecord] = []

    async def acompletion(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: str = "auto",
    ) -> LLMResponse:
        self.calls.append(_StubCallRecord(messages=list(messages), tools=list(tools)))
        if not self._responses:
            raise StubExhaustedError("StubLiteLLM exhausted")
        return self._responses.pop(0)


class LiteLLMClient:
    def __init__(
        self,
        *,
        model: str,
        api_base: str,
        api_key: str,
        request_timeout_s: int = 120,
    ) -> None:
        self._model = model
        self._api_base = api_base
        self._api_key = api_key
        self._timeout = request_timeout_s

    async def acompletion(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: str = "auto",
    ) -> LLMResponse:
        import json
        import litellm  # local import keeps the dep optional for unit tests

        resp = await litellm.acompletion(
            model=self._model,
            api_base=self._api_base,
            api_key=self._api_key,
            messages=messages,
            tools=tools or None,
            tool_choice=tool_choice if tools else None,
            timeout=self._timeout,
        )
        msg = resp.choices[0].message
        tcs: list[LLMToolCall] = []
        for raw in (msg.tool_calls or []):
            try:
                args: dict[str, Any] = json.loads(raw.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tcs.append(LLMToolCall(id=raw.id, name=raw.function.name, arguments=args))
        return LLMResponse(content=msg.content, tool_calls=tcs, raw=resp)
