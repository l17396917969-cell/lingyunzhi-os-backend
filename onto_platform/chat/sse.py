from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import AsyncIterator, Any


def sse_format(event_type: str, payload: Any) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


class _Subscription:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[tuple[str, Any] | None] = asyncio.Queue()


@dataclass
class _TurnState:
    subs: list[_Subscription] = field(default_factory=list)
    buffer: list[tuple[str, Any]] = field(default_factory=list)
    closed: bool = False


# How long after close() to retain the per-turn buffer for late subscribers.
# Long enough to absorb a slow client connecting after a fast turn (the common race
# we're guarding against), short enough that abandoned turns don't accumulate.
_RETAIN_AFTER_CLOSE_S = 60


class EventBus:
    """In-process pub/sub keyed by turn_id with replay buffer.

    All events published for a given turn_id are buffered until the first
    subscriber finishes draining them or the turn is closed and retained for
    `_RETAIN_AFTER_CLOSE_S` seconds (whichever comes first).

    This guards against the race where the SSE consumer subscribes after the
    background worker has already published events — common for short turns
    that complete before the HTTP /stream handler runs.
    """

    def __init__(self) -> None:
        self._turns: dict[str, _TurnState] = {}

    def _state(self, turn_id: str) -> _TurnState:
        return self._turns.setdefault(turn_id, _TurnState())

    async def subscribe(self, turn_id: str) -> AsyncIterator[tuple[str, Any]]:
        state = self._state(turn_id)
        sub = _Subscription()
        # Replay buffered events first so late subscribers see what they missed.
        for ev in list(state.buffer):
            await sub.queue.put(ev)
        # If the turn is already closed, queue the sentinel so the iterator returns
        # after replaying — no more events are coming.
        if state.closed:
            await sub.queue.put(None)
        # Register for any future events (only meaningful when not yet closed).
        state.subs.append(sub)
        try:
            while True:
                item = await sub.queue.get()
                if item is None:
                    return
                yield item
        finally:
            if sub in state.subs:
                state.subs.remove(sub)

    async def publish(self, turn_id: str, event_type: str, payload: Any) -> None:
        state = self._state(turn_id)
        if state.closed:
            # Don't accept publishes after close — the turn is finalized.
            return
        ev = (event_type, payload)
        state.buffer.append(ev)
        for sub in list(state.subs):
            await sub.queue.put(ev)

    async def close(self, turn_id: str) -> None:
        state = self._turns.get(turn_id)
        if state is None or state.closed:
            return
        state.closed = True
        for sub in list(state.subs):
            await sub.queue.put(None)
        # Schedule cleanup so closed turn states don't accumulate forever.
        # The buffer remains available for late subscribers until cleanup fires.
        asyncio.create_task(self._cleanup_after(turn_id, _RETAIN_AFTER_CLOSE_S))

    async def _cleanup_after(self, turn_id: str, delay_s: int) -> None:
        try:
            await asyncio.sleep(delay_s)
        except asyncio.CancelledError:
            return
        # Only drop the state if no live subscribers are still iterating.
        state = self._turns.get(turn_id)
        if state is None:
            return
        if not state.subs:
            self._turns.pop(turn_id, None)
