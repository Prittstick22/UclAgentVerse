"""Read-only recorded demo playback; never execute the simulator or an agent."""
from __future__ import annotations

import asyncio
import json
import math
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.clock import SimClock
from app.core.db import DB
from app.core.events import Event, EventBus
from app.engine.portfolio import checkpoints
from app.schemas import Mandate, Proposal
from app.sim.controller import SimController, SimError
from app.sim.controller import controller as simulation_controller

if TYPE_CHECKING:
    from app.container import AppState


def recorded_database(path: Path) -> DB:
    """Open an existing recording read-only and copy it; never modify the original."""
    db = DB(":memory:")
    with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as source:
        source.backup(db.conn)
    return db


class RecordedEvents(EventBus):
    def subscribe(self, run_id: str | None = None) -> asyncio.Queue:
        # A finite saved log can be replayed faster than a browser consumes it; do not drop its events.
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append((queue, run_id))
        return queue

    def history(self, run_id: str | None = None, after: int = 0, limit: int = 1_000_000) -> list[Event]:
        clause = " AND run_id=?" if run_id is not None else ""
        args = (self.clock.as_of_str(), after, *([run_id] if run_id is not None else []), limit)
        rows = self.db.execute(
            "SELECT json FROM events WHERE mode='historical' AND as_of<=? AND seq>?"
            + clause + " ORDER BY as_of, rowid LIMIT ?", args,
        )
        return [Event.model_validate_json(row[0]) for row in rows]

    def publish_recorded(self, event: Event) -> None:
        # Already persisted by the original run. Do not re-emit, assign new IDs or trigger tool listeners.
        for queue, run_id in list(self._subscribers):
            if run_id is None or run_id == event.run_id:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass


class RecordedReplay:
    def __init__(self, state: AppState):
        if not isinstance(state.clock, SimClock) or not isinstance(state.events, RecordedEvents):
            raise ValueError("Recorded playback needs a historical clock and recorded event bus")
        self.state = state
        self.clock = state.clock
        self.bus = state.events
        raw = state.db.get("sim_results", "latest")
        if not raw:
            raise ValueError("RECORDED_RUN must contain a finished simulation")
        result = json.loads(raw)
        self.start_day, self.end_day = result["start"], result["end"]
        self.events: dict[str, list[Event]] = {}
        for (raw_event,) in state.db.execute(
            "SELECT json FROM events WHERE mode='historical' ORDER BY as_of, rowid"
        ):
            event = Event.model_validate_json(raw_event)
            self.events.setdefault(event.as_of, []).append(event)
        self.construction = next((event for events in self.events.values() for event in events
                                  if event.type == "run.started"
                                  and (event.trigger_kind or event.payload.get("kind")) == "construction"), None)
        self.days = sorted(day for day, events in self.events.items() if any(e.type == "clock.tick" for e in events))
        marks = {mark.date for mark in checkpoints(state.db, "historical")}
        if (not self.days or self.days[0] != self.start_day or self.days[-1] != self.end_day
                or set(self.days) != marks or len(self.days) != result["days"]
                or any(sum(event.type == "clock.tick" for event in self.events[day]) != 1 for day in self.days)):
            raise ValueError("RECORDED_RUN needs complete dated events and ledger checkpoints")
        raw_mandate = state.db.get("sim_mandate", "initial")
        if not raw_mandate or Mandate.model_validate_json(raw_mandate) != state.mandate:
            raise ValueError("RECORDED_RUN needs an initial mandate matching the fixed demo persona")
        state.proposals.update({key: Proposal.model_validate_json(value) for key, value in state.db.list("proposals")})
        self.clock.set(self.end_day)
        from app.sim.evaluate import benchmarks_payload

        self.benchmarks = benchmarks_payload(state.db)
        self.selected = self.days
        self.index = len(self.selected)
        self.speed = 1.0
        self.task: asyncio.Task | None = None
        self.stop = asyncio.Event()
        self.started = False

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    def info(self) -> dict:
        return {"running": self.running, "speed": self.speed,
                "start": self.selected[0], "end": self.selected[-1]}

    def progress(self) -> float:
        return self.index / len(self.selected)

    def visible_proposal(self, proposal_id: str) -> Proposal | None:
        proposal = self.state.proposals.get(proposal_id)
        day = self.state.clock.as_of_str()
        if proposal is None or proposal.as_of > day:
            return None
        if day >= self.end_day:
            return proposal
        # The kv store is the final version. Do not show a later approval/execution while rewound.
        status = "draft"
        selected = proposal.selected
        created = False
        approved_day = None
        uncertainties = [note for note in proposal.uncertainties if not note.startswith("Declined: ")]
        for event_day, events in self.events.items():
            if event_day > day:
                break
            for event in events:
                if (not created and event.run_id == proposal.run_id and event.type == "tool.call"
                        and event.payload.get("tool") == "propose_adjustment"):
                    selected = event.payload.get("args", {}).get("option") or "recommended"
                if (status == "approved" and proposal.status == "executed" and approved_day
                        and event.type == "order.filled" and event_day > approved_day):
                    status = "executed"
                if event.payload.get("proposal_id") != proposal_id:
                    continue
                if event.type == "proposal.created":
                    created = True
                if event.type == "approval.requested":
                    status = "awaiting_approval"
                elif event.type == "approval.decided":
                    status = "declined" if event.payload.get("decision") in ("decline", "declined") else "approved"
                    selected = event.payload.get("option", selected)
                    approved_day = event_day if status == "approved" else None
                    if status == "declined" and event.payload.get("reason"):
                        uncertainties.append(f"Declined: {event.payload['reason']}")
                elif event.type == "gate.verdict" and event.status == "failed":
                    status = "blocked"
        return proposal.model_copy(update={"status": status, "selected": selected, "uncertainties": uncertainties})

    async def start(self, start: str | None = None, end: str | None = None, speed: float | None = None,
                    run_agents: bool = False, approvals: str = "manual") -> dict:
        if self.running:
            raise SimError(409, "conflict", "The replay is already running; pause it first")
        if speed is not None and (not math.isfinite(speed) or speed < 0):
            raise SimError(422, "validation_error", "speed must be finite and at least 0")
        first, last = start or self.start_day, end or self.end_day
        if first < self.start_day or last > self.end_day or first > last:
            raise SimError(422, "validation_error", "Replay dates must stay within the recorded window")
        selected = [day for day in self.days if first <= day <= last]
        if not selected:
            raise SimError(422, "validation_error", "No recorded trading days in that range")
        self.selected, self.index = selected, 0
        self.started = True
        self.speed = float(speed) if speed is not None else self.speed
        self.clock.set(self.selected[0])
        self.stop = asyncio.Event()
        self.task = asyncio.create_task(self._loop())
        return self.info()

    async def _loop(self) -> None:
        while self.index < len(self.selected) and not self.stop.is_set():
            self._advance()
            if self.index >= len(self.selected):
                break
            try:
                await asyncio.wait_for(self.stop.wait(), timeout=1 / self.speed if self.speed else 0)
            except TimeoutError:
                pass

    def _advance(self) -> None:
        day = self.selected[self.index]
        self.clock.set(day)
        for event in self.events[day]:
            self.bus.publish_recorded(event)
        self.index += 1

    async def pause(self) -> dict:
        self.stop.set()
        if self.running:
            await self.task
        return self.info()

    async def step(self, days: int = 1) -> dict:
        if days < 1:
            raise SimError(422, "validation_error", "days must be at least 1")
        if self.running:
            raise SimError(409, "conflict", "Pause the replay before stepping")
        if not self.started:
            self.index = 0
            self.started = True
        for _ in range(days):
            if self.index >= len(self.selected):
                break
            self._advance()
        return self.info()


def controller(state: AppState) -> RecordedReplay | SimController:
    return state.recording if state.recording is not None else simulation_controller(state)
