#!/usr/bin/env python3
"""Generate fixtures/ for the frontend mock mode from a fake construction run + sample API responses.

    python scripts/make_fixtures.py     (needs a snapshot: run make_synthetic_snapshot.py first)
    python scripts/make_fixtures.py --from-db <live run>.sqlite   # a recorded real Argon run (no LLM calls)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import tempfile
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.container import build_state  # noqa: E402
from app.engine.portfolio import record_checkpoint  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import Settings  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "fixtures"


def profile_fixtures(c: TestClient) -> None:
    for name, path in {"demo_profile": "/api/profile/demo", "mandate": "/api/mandate"}.items():
        response = c.get(path)
        response.raise_for_status()
        (OUT / f"{name}.json").write_text(json.dumps(response.json(), indent=1) + "\n", encoding="utf-8")
    c.post("/api/mode", json={"mode": "live"}).raise_for_status()
    quiz = c.post("/api/profile/quiz", json={"answers": {"horizon": "gt15", "emergency": "yes", "loss_goal": "no",
                                                         "income": "steady", "reaction": "hold", "swings": "wide",
                                                         "experience": "never", "worry": "weekly"}})
    quiz.raise_for_status()
    (OUT / "quiz_result.json").write_text(json.dumps(quiz.json(), indent=1) + "\n", encoding="utf-8")
    c.post("/api/mode", json={"mode": "historical"}).raise_for_status()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from-db", help="SQLite of a recorded real construction run: use its events/proposal (no LLM)")
    ap.add_argument("--profiles-only", action="store_true", help="refresh profile fixtures without unrelated run IDs")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    if a.from_db:  # work on a copy so the recording is never modified
        copy = Path(tempfile.mkdtemp()) / "recorded.sqlite"
        shutil.copy(a.from_db, copy)
        state = build_state(Settings(llm_mode="replay", app_mode="historical"), db_path=str(copy))
        starts = [e for e in state.events.history(None) if e.type == "run.started" and e.trigger_kind == "construction"]
        if not starts:
            raise SystemExit("No construction run in that database; fixtures NOT written.")
        run_id = starts[-1].run_id
        done = [e for e in state.events.history(run_id) if e.type == "run.completed"]
        proposal_id = done[-1].payload.get("proposal_id") if done else None
        if not proposal_id or not state.db.get("proposals", proposal_id):
            raise SystemExit("That run has no stored proposal; fixtures NOT written.")
        from app.schemas import Proposal
        state.proposals[proposal_id] = Proposal.model_validate_json(state.db.get("proposals", proposal_id))
        run = SimpleNamespace(run_id=run_id, proposal_id=proposal_id)
    else:
        state = build_state(Settings(llm_mode="fake", app_mode="historical"), db_path=":memory:")
    app.state.app = state
    c = TestClient(app)
    if a.profiles_only:
        profile_fixtures(c)
        return
    if not a.from_db:
        run = asyncio.run(state.supervisor.start("construction", "User asked to build a portfolio"))
    events = [e.model_dump() for e in state.events.history(run.run_id)]
    (OUT / "events_construction.json").write_text(json.dumps(events, indent=1))
    for name, path in {
        "health": "/api/health", "questions": "/api/profile/questions", "mandate": "/api/mandate",
        "catalogue": "/api/catalogue", "correlation": "/api/risk/correlation",
        "runs": "/api/runs", "run_detail": f"/api/runs/{run.run_id}", "benchmarks": "/api/benchmarks",
        "notifications": "/api/notifications",
    }.items():
        r = c.get(path)
        (OUT / f"{name}.json").write_text(json.dumps(r.json(), indent=1))
    # Example paper execution using the fake proposal's targets and the offline ledger.
    if run.proposal_id:
        proposal = state.proposals[run.proposal_id]
        option = next(option for option in proposal.options if option.label == proposal.selected)
        weights = {holding.ticker: holding.weight for holding in option.holdings}
        start = state.clock.as_of_str()
        ledger = state.ledger
        ledger.deposit(state.mandate.goal.starting_amount_gbp)
        ledger.queue_rebalance(weights, "Example construction")
        record_checkpoint(state.db, "historical", ledger, start, weights)
        state.events.emit("approval.decided", run_id=run.run_id, title="Example approval",
                          payload={"proposal_id": proposal.id, "decision": "approved", "by": "user"})
        for day in state.gw.trading_days(start)[1:4]:
            state.clock.set(day.date())
            date = state.clock.as_of_str()
            prices = state.gw.latest_prices().to_dict()
            for fill in ledger.fill_pending(date, prices):
                state.events.emit("order.filled", run_id=run.run_id, title="Example fill", payload=vars(fill))
            ledger.mark_to_market(prices)
            record_checkpoint(state.db, "historical", ledger, date, weights)
    for name, path in {
        "portfolio": "/api/portfolio", "history": "/api/portfolio/history",
        "pnl": "/api/portfolio/pnl", "rebalances": "/api/portfolio/rebalances",
    }.items():
        response = c.get(path)
        response.raise_for_status()
        (OUT / f"{name}.json").write_text(json.dumps(response.json(), indent=1) + "\n", encoding="utf-8")
    profile_fixtures(c)
    print(f"Wrote fixtures to {OUT} ({len(events)} events)")


if __name__ == "__main__":
    main()
