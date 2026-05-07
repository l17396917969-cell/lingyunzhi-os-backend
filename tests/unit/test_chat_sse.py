import asyncio
import json
import pytest
from onto_platform.chat.sse import EventBus, sse_format

pytestmark = pytest.mark.asyncio


def test_sse_format_serializes_event_and_data():
    s = sse_format("tool_call", {"name": "put_object_type"})
    assert s.startswith("event: tool_call\n")
    assert "data: " in s
    assert s.endswith("\n\n")
    data_line = next(ln for ln in s.splitlines() if ln.startswith("data: "))
    assert json.loads(data_line[len("data: "):])["name"] == "put_object_type"


async def test_event_bus_fan_out_to_two_consumers():
    bus = EventBus()
    out_a: list[tuple[str, dict]] = []
    out_b: list[tuple[str, dict]] = []

    async def consumer(target):
        async for event_type, payload in bus.subscribe("turn-1"):
            target.append((event_type, payload))

    a = asyncio.create_task(consumer(out_a))
    b = asyncio.create_task(consumer(out_b))
    await asyncio.sleep(0.05)  # let subscribers register
    await bus.publish("turn-1", "tool_call", {"name": "x"})
    await bus.publish("turn-1", "turn_complete", {"tool_calls_made": 1})
    await bus.close("turn-1")
    await asyncio.gather(a, b)
    assert out_a == [("tool_call", {"name": "x"}), ("turn_complete", {"tool_calls_made": 1})]
    assert out_b == out_a


async def test_event_bus_replays_buffered_events_to_late_subscriber():
    """Events published before any subscriber must be replayed when one finally connects.

    This is the production race we hit on tencent-xianyu: the background worker
    finished a fast LLM-failed turn before the SSE handler subscribed, so the
    client hung forever waiting for events that had already been emitted.
    """
    bus = EventBus()
    # Worker publishes everything before any subscriber connects
    await bus.publish("turn-X", "turn_start", {"turn_id": "X"})
    await bus.publish("turn-X", "tool_call", {"sequence": 1, "name": "put_object_type"})
    await bus.publish("turn-X", "turn_error", {"kind": "llm_error", "message": "boom"})
    await bus.close("turn-X")

    # Late subscriber: should still receive all events plus a clean iterator close
    out: list[tuple[str, dict]] = []
    async for event_type, payload in bus.subscribe("turn-X"):
        out.append((event_type, payload))

    types = [t for t, _ in out]
    assert types == ["turn_start", "tool_call", "turn_error"]
    assert out[1][1]["name"] == "put_object_type"


async def test_event_bus_mid_turn_subscriber_gets_buffered_plus_live():
    """A subscriber that connects mid-turn must see prior buffered events AND
    subsequent live events, in order."""
    bus = EventBus()
    await bus.publish("turn-Y", "turn_start", {})
    await bus.publish("turn-Y", "tool_call", {"sequence": 1})

    out: list[tuple[str, dict]] = []

    async def consume():
        async for ev in bus.subscribe("turn-Y"):
            out.append(ev)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)  # let subscribe() drain the buffer + register

    # More events arrive after the subscriber registers
    await bus.publish("turn-Y", "tool_call", {"sequence": 2})
    await bus.publish("turn-Y", "turn_complete", {"tool_calls_made": 2})
    await bus.close("turn-Y")
    await task

    types = [t for t, _ in out]
    assert types == ["turn_start", "tool_call", "tool_call", "turn_complete"]
    sequences = [p.get("sequence") for t, p in out if t == "tool_call"]
    assert sequences == [1, 2]


async def test_event_bus_publish_after_close_is_dropped():
    """close() finalizes a turn — subsequent publishes must be ignored, not
    silently buffered (which would leak into a re-used turn_id later)."""
    bus = EventBus()
    await bus.publish("turn-Z", "turn_start", {})
    await bus.close("turn-Z")
    # Late publish must not corrupt the buffer
    await bus.publish("turn-Z", "tool_call", {"sequence": 99})

    out: list[tuple[str, dict]] = []
    async for ev in bus.subscribe("turn-Z"):
        out.append(ev)

    assert [t for t, _ in out] == ["turn_start"]


async def test_event_bus_close_is_idempotent():
    """Calling close() twice on the same turn must not raise or duplicate sentinels."""
    bus = EventBus()
    await bus.publish("turn-W", "turn_start", {})
    await bus.close("turn-W")
    await bus.close("turn-W")  # second close is a no-op

    out: list[tuple[str, dict]] = []
    async for ev in bus.subscribe("turn-W"):
        out.append(ev)
    assert [t for t, _ in out] == ["turn_start"]
