#!/usr/bin/env python3
"""Generate fixtures/ for the frontend mock mode from a fake construction run + sample API responses.

    python scripts/make_fixtures.py     (needs a snapshot: run make_synthetic_snapshot.py first)
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.container import build_state  # noqa: E402
from app.main import app  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "fixtures"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    state = build_state(db_path=":memory:")
    app.state.app = state
    run = asyncio.run(state.supervisor.start("construction", "User asked to build a portfolio"))
    events = [e.model_dump() for e in state.events.history(run.run_id)]
    (OUT / "events_construction.json").write_text(json.dumps(events, indent=1))
    c = TestClient(app)
    for name, path in {
        "health": "/api/health", "questions": "/api/profile/questions", "mandate": "/api/mandate",
        "catalogue": "/api/catalogue", "portfolio": "/api/portfolio", "correlation": "/api/risk/correlation",
        "runs": "/api/runs", "run_detail": f"/api/runs/{run.run_id}", "benchmarks": "/api/benchmarks",
        "pnl": "/api/portfolio/pnl", "rebalances": "/api/portfolio/rebalances", "notifications": "/api/notifications",
    }.items():
        r = c.get(path)
        (OUT / f"{name}.json").write_text(json.dumps(r.json(), indent=1))
    quiz = c.post("/api/profile/quiz", json={"answers": {"horizon": "gt15", "emergency": "yes", "loss_goal": "no",
                                                         "income": "steady", "reaction": "hold", "swings": "wide",
                                                         "experience": "never", "worry": "weekly"}})
    (OUT / "quiz_result.json").write_text(json.dumps(quiz.json(), indent=1))
    print(f"Wrote fixtures to {OUT} ({len(events)} events)")


if __name__ == "__main__":
    main()
