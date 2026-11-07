"""Wires the app together: clock, db, events, gateway, ledger, LLM, supervisor. Owner: Jin (wiring) / all."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.fakes import FakeBrain
from app.agents.llm import LLM
from app.agents.supervisor import Supervisor
from app.agents.tools import ToolContext, default_registry
from app.config import params
from app.core.clock import Clock, LiveClock, SimClock
from app.core.db import DB
from app.core.events import EventBus
from app.data.gateway import DataGateway
from app.data.snapshot import load_snapshot
from app.engine.ledger import Ledger
from app.profile.quiz import mandate_for
from app.schemas import Mandate
from app.settings import Settings, get_settings


@dataclass
class AppState:
    settings: Settings
    clock: Clock
    db: DB
    events: EventBus
    gw: DataGateway
    ledger: Ledger
    mandate: Mandate
    llm: LLM
    supervisor: Supervisor
    proposals: dict = field(default_factory=dict)
    runs: dict = field(default_factory=dict)


def build_state(settings: Settings | None = None, db_path: str | None = None) -> AppState:
    s = settings or get_settings()
    clock: Clock = SimClock(params()["sim"]["start"]) if s.app_mode == "historical" else LiveClock()
    db = DB(db_path or s.state_db)
    events = EventBus(db, clock)
    gw = DataGateway(clock, load_snapshot(s.snapshot_dir), events)
    ledger = Ledger(catalogue={i.ticker: i for i in gw.catalogue(eligible_only=False)})
    llm = LLM(db, s, fake=FakeBrain())
    state = AppState(settings=s, clock=clock, db=db, events=events, gw=gw, ledger=ledger,
                     mandate=mandate_for("balanced"), llm=llm, supervisor=None)  # type: ignore[arg-type]
    tools = default_registry(ToolContext(gw=gw, events=events, state=state))
    state.supervisor = Supervisor(llm, tools, events)
    return state
