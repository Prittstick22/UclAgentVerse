"""Sim controls for the API (#22): start / pause / step / status. Owner: Cem. Contract: docs/04 §3 (sim rows).

One controller per historical AppState. `start` replays from a fresh ledger as a background task at `speed`
trading days per second (0 = as fast as possible); `pause` stops after the current day; `step` advances N days
while paused. Live mode has no simulator.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import params
from app.engine.ledger import Ledger
from app.sim.approvals import ApprovalMode
from app.sim.runner import Simulation

log = logging.getLogger(__name__)


class SimError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class SimController:
    def __init__(self, state: Any):
        self.state = state
        self.sim: Simulation | None = None
        self.task: asyncio.Task | None = None
        self.speed: float = 1.0
        self.error: str | None = None
        self._stop = asyncio.Event()

    # ------------------------------------------------------------------ views
    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    def info(self) -> dict:
        s = self.sim
        return {"running": self.running, "speed": self.speed,
                "start": s.res.start if s else None, "end": s.res.end if s else None}

    def progress(self) -> float:
        return self.sim.progress if self.sim else 0.0

    # ------------------------------------------------------------------ controls
    def _check_mode(self) -> None:
        if self.state.clock.mode != "historical":
            raise SimError(409, "conflict", "The simulator only runs in historical mode")

    def _new(self, start: str | None, end: str | None, run_agents: bool, approvals: ApprovalMode) -> None:
        st = self.state
        for p in st.proposals.values():          # proposals from an earlier replay can't be approved any more
            if p.status in ("draft", "awaiting_approval"):
                p.status = "expired"
                st.db.put("proposals", p.id, p.model_dump_json())
        # a new replay starts a new portfolio history (old days would otherwise linger past the new end date)
        st.db.execute("DELETE FROM kv WHERE ns=?", (f"ledger_checkpoints:{st.clock.mode}",))
        st.ledger = Ledger(catalogue={i.ticker: i for i in st.gw.catalogue(eligible_only=False)})
        try:
            self.sim = Simulation(st, start or params()["sim"]["start"], end or params()["sim"]["end"],
                                  agents=run_agents, approvals=approvals)
        except ValueError as e:
            raise SimError(422, "validation_error", str(e)) from None
        self.error = None

    async def start(self, start: str | None = None, end: str | None = None, speed: float | None = None,
                    run_agents: bool = False, approvals: ApprovalMode = "manual") -> dict:
        self._check_mode()
        if self.running:
            raise SimError(409, "conflict", "The simulation is already running; pause it first")
        if speed is not None:
            if speed < 0:
                raise SimError(422, "validation_error", "speed must be 0 (as fast as possible) or more")
            self.speed = float(speed)
        self._new(start, end, run_agents, approvals)
        self._launch()
        return self.info()

    async def resume(self, speed: float | None = None) -> dict:
        self._check_mode()
        if self.sim is None or self.sim.done:
            raise SimError(409, "conflict", "Nothing to resume; start a simulation")
        if speed is not None:
            self.speed = float(speed)
        if not self.running:
            self._launch()
        return self.info()

    async def pause(self, wait_s: float = 2.0) -> dict:
        """Stops after the day in progress (a day is never left half-simulated). Returns within `wait_s`;
        if an agent run is still finishing that day, `running` stays true until it does."""
        if self.running:
            self._stop.set()
            try:
                await asyncio.wait_for(asyncio.shield(self.task), timeout=wait_s)
            except TimeoutError:
                pass
        return self.info()

    def _launch(self) -> None:
        self._stop = asyncio.Event()
        self.task = asyncio.create_task(self._loop())

    async def step(self, days: int = 1) -> dict:
        self._check_mode()
        if days < 1:
            raise SimError(422, "validation_error", "days must be at least 1")
        if self.running:
            raise SimError(409, "conflict", "Pause the simulation before stepping")
        if self.sim is None:
            self._new(None, None, False, "manual")
        for _ in range(days):
            if self.sim.done:
                break
            await self.sim.step()
        return self.info()

    async def _loop(self) -> None:
        try:
            while self.sim is not None and not self.sim.done and not self._stop.is_set():
                await self.sim.step()
                delay = 1.0 / self.speed if self.speed > 0 else 0.0
                try:   # sleep between days, but wake at once on pause
                    await asyncio.wait_for(self._stop.wait(), timeout=delay)
                except TimeoutError:
                    pass
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            log.exception("simulation failed")


def controller(state: Any) -> SimController:
    ctl = getattr(state, "sim_controller", None)
    if ctl is None:
        ctl = SimController(state)
        state.sim_controller = ctl
    return ctl
