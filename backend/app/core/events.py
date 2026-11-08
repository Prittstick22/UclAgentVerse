"""Typed, append-only event log + pub/sub for SSE. CONTRACT FILE: see docs/04-api-contracts.md §3."""
from __future__ import annotations

import asyncio
import itertools
import json
import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.clock import Clock
from app.core.db import DB

logger = logging.getLogger(__name__)

EventType = Literal[
    "run.started", "run.completed",
    "agent.spawn_requested", "agent.spawned", "agent.spawn_denied", "agent.status", "agent.message",
    "tool.call", "tool.result", "source.inspect", "calc.result", "finding",
    "gate.started", "gate.verdict", "revision.requested", "content.quarantined", "budget.exceeded",
    "asof.violation", "decision.made", "proposal.created", "approval.requested", "approval.decided",
    "order.filled", "monitor.fired", "monitor.created", "monitor.shadow_result", "monitor.activated",
    "monitor.disabled", "rule.proposed", "rule.tested", "rule.promoted", "rule.applied",
    "clock.tick", "mode.changed", "notification.created",
]


class Event(BaseModel):
    id: str
    run_id: str | None = None
    seq: int
    ts_wall: str
    as_of: str
    mode: Literal["historical", "live"]
    type: EventType
    agent_id: str | None = None
    parent_agent_id: str | None = None
    depth: int | None = None
    role: str | None = None
    title: str
    purpose: str | None = None
    status: Literal["started", "running", "ok", "failed", "denied"] | None = None
    trigger_kind: str | None = None
    trigger_text: str | None = None
    case_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class EventBus:
    """emit() persists to SQLite and fans out to async subscribers (SSE)."""

    def __init__(self, db: DB, clock: Clock):
        self.db = db
        self.clock = clock
        self._seq: dict[str | None, itertools.count] = {}
        self._subscribers: list[tuple[asyncio.Queue, str | None]] = []
        self._listeners: list[Callable[[Event], None]] = []

    def _next_seq(self, run_id: str | None) -> int:
        if run_id not in self._seq:
            rows = self.db.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM events WHERE run_id IS ?", (run_id,)
            )
            self._seq[run_id] = itertools.count(rows[0][0] + 1)
        return next(self._seq[run_id])

    def emit(self, type: EventType, *, title: str, run_id: str | None = None, **fields: Any) -> Event:
        ev = Event(
            id=uuid.uuid4().hex,
            run_id=run_id,
            seq=self._next_seq(run_id),
            ts_wall=datetime.now(timezone.utc).isoformat(),
            as_of=self.clock.as_of_str(),
            mode=self.clock.mode,  # type: ignore[arg-type]
            type=type,
            title=title,
            **fields,
        )
        self.db.execute(
            "INSERT INTO events(id, run_id, seq, ts_wall, as_of, mode, type, json) VALUES (?,?,?,?,?,?,?,?)",
            (ev.id, ev.run_id, ev.seq, ev.ts_wall, ev.as_of, ev.mode, ev.type, ev.model_dump_json()),
        )
        for queue, filter_run in list(self._subscribers):
            if filter_run is None or filter_run == run_id:
                try:
                    queue.put_nowait(ev)
                except asyncio.QueueFull:  # slow client; drop
                    pass
        for listener in self._listeners:
            try:
                listener(ev)
            except Exception:
                logger.exception("Event listener failed after recording %s (%s)", ev.type, ev.id)
        return ev

    def listen(self, listener: Callable[[Event], None]) -> None:
        self._listeners.append(listener)

    def history(self, run_id: str | None = None, after: int = 0, limit: int = 5000) -> list[Event]:
        if run_id is None:
            rows = self.db.execute("SELECT json FROM events ORDER BY ts_wall LIMIT ?", (limit,))
        else:
            rows = self.db.execute(
                "SELECT json FROM events WHERE run_id=? AND seq>? ORDER BY seq LIMIT ?", (run_id, after, limit)
            )
        return [Event.model_validate_json(r[0]) for r in rows]

    def subscribe(self, run_id: str | None = None) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers.append((q, run_id))
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers = [(qq, r) for qq, r in self._subscribers if qq is not q]


def sse_frame(ev: Event) -> str:
    return f"event: {ev.type}\ndata: {json.dumps(ev.model_dump())}\n\n"
