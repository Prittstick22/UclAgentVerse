"""Wires the app together: clock, db, events, gateway, ledger, LLM, supervisor. Owner: Jin (wiring) / all."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.agents.fakes import FakeBrain
from app.agents.llm import LLM
from app.agents.supervisor import Supervisor
from app.agents.tools import ToolContext, default_registry
from app.api.notifications import PortfolioActivity
from app.config import params
from app.core.clock import Clock, LiveClock, SimClock
from app.core.db import DB
from app.core.events import EventBus
from app.data.gateway import DataGateway
from app.data.live import LiveUpdates
from app.data.snapshot import load_snapshot
from app.engine.ledger import Ledger
from app.profile.quiz import mandate_for
from app.schemas import Mandate
from app.settings import Settings, get_settings
from app.sim import approvals


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
    modes: dict[str, AppState] = field(default_factory=dict, repr=False)
    live_updates: LiveUpdates | None = field(default=None, repr=False)
    activity: PortfolioActivity = field(init=False)


def build_state(settings: Settings | None = None, db_path: str | None = None) -> AppState:
    s = settings or get_settings()
    clock: Clock = SimClock(params()["sim"]["start"]) if s.app_mode == "historical" else LiveClock()
    db = DB(db_path or s.state_db)
    events = EventBus(db, clock)
    live_dir = s.snapshot_dir / "live"
    snapshot_path = live_dir if s.app_mode == "live" and (live_dir / "prices_daily.parquet").exists() else s.snapshot_dir
    gw = DataGateway(clock, load_snapshot(snapshot_path), events)
    ledger = Ledger(catalogue={i.ticker: i for i in gw.catalogue(eligible_only=False)})
    llm = LLM(db, s, fake=FakeBrain())
    state = AppState(settings=s, clock=clock, db=db, events=events, gw=gw, ledger=ledger,
                     mandate=mandate_for("balanced"), llm=llm, supervisor=None)  # type: ignore[arg-type]
    tools = default_registry(ToolContext(gw=gw, events=events, state=state))
    state.supervisor = Supervisor(llm, tools, events)
    state.modes[s.app_mode] = state
    if s.app_mode == "live":
        state.live_updates = LiveUpdates(state)
    state.activity = PortfolioActivity(state)
    approvals.attach(state)   # records mandate + holdings when each proposal is made (#23 revalidation)
    return state


def state_for_mode(state: AppState, mode: str) -> AppState:
    """Separate clocks, caches, ledgers, proposals and DBs for historical/live work."""
    if mode not in state.modes:
        db_path = state.db.path
        if db_path != ":memory:":
            # Both modes derive from the original configured DB, not a nested suffix.
            original = Path(state.settings.state_db)
            db_path = str(original.with_name(f"{original.stem}.{mode}{original.suffix}"))
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        other = build_state(state.settings.model_copy(update={"app_mode": mode}), db_path=db_path)
        other.modes = state.modes
        state.modes[mode] = other
    return state.modes[mode]
