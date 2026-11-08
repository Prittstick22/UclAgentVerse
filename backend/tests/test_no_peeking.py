"""Walk-forward integrity (#72), a judged control.

On every simulated day the system must not know what happens next. For several cut-off days t we run the
simulator (engine-only and with fake-LLM agents + batch approvals) on:
  (a) the full snapshot, to the end of the window,
  (b) a snapshot with everything after t DELETED (prices, FX, news, filings), run to t,
  (c) a snapshot with every price and FX rate after t SCRAMBLED (random walk), run to the end,
and require every event up to and including t to be identical: weights, NAV, orders, triggers, decisions,
forecasts, proposals and approvals. A leaky gateway must make this fail (last test).

Deck line: "Walk-forward verified: deleting or scrambling future data changes nothing before that date."
"""
from __future__ import annotations

import asyncio
import json
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.config import params
from app.container import build_state
from app.core.events import Event
from app.data.gateway import DataGateway
from app.settings import Settings
from app.sim import runner

START = params()["sim"]["start"]
CUT_OFFSETS = (12, 37, 63)          # trading days into the window: early, middle, late (spans reviews + a month end)
VOLATILE = re.compile(r"(prop|run|conv)_[0-9a-f]{6,}|calc:[0-9a-f]{8,}|[0-9a-f]{32}")
DROP_KEYS = {"duration_s", "ts_wall", "started_at", "finished_at"}


def _scrub(x):
    if isinstance(x, dict):
        return {k: _scrub(v) for k, v in sorted(x.items()) if k not in DROP_KEYS}
    if isinstance(x, list):
        return [_scrub(v) for v in x]
    if isinstance(x, str):
        return VOLATILE.sub("<id>", x)
    return x


def _trace(state, upto: str) -> list[str]:
    """Every event dated <= upto, without ids and wall-clock fields, in emission order."""
    out = []
    # insertion order (rowid), not ts_wall: two events in the same microsecond would otherwise flip order
    rows = state.db.execute("SELECT json FROM events ORDER BY rowid")
    for e in (Event.model_validate_json(r[0]) for r in rows):
        if e.as_of[:10] > upto:
            continue
        out.append(json.dumps(_scrub({"type": e.type, "as_of": e.as_of[:10], "title": e.title, "status": e.status,
                                      "trigger_kind": getattr(e, "trigger_kind", None),
                                      "trigger_text": getattr(e, "trigger_text", None), "payload": e.payload}),
                              sort_keys=True, default=str))
    return out


def _simulate(snapshot_dir: Path, end: str | None, agents: bool) -> list:
    state = build_state(Settings(snapshot_dir=snapshot_dir, llm_mode="fake", app_mode="historical"), db_path=":memory:")
    asyncio.run(runner.run(state, START, end, agents=agents, approvals="batch_policy"))
    return state


def _rewrite(src: Path, dst: Path, cut: str, how: str) -> Path:
    """Copy a snapshot, then delete or scramble everything dated after `cut`."""
    shutil.copytree(src, dst)
    px = pd.read_parquet(src / "prices_daily.parquet")
    fx = pd.read_parquet(src / "fx_daily.parquet")
    after_px, after_fx = px["date"].astype(str) > cut, fx["date"].astype(str) > cut
    if how == "delete":
        px, fx = px[~after_px], fx[~after_fx]
        for name, key in (("news.jsonl", "available_at"), ("filings.jsonl", "available_at"),
                          ("earnings.jsonl", "date")):
            f = dst / name
            if f.exists():
                rows = [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
                keep = [r for r in rows if str(r.get(key, ""))[:10] <= cut]
                f.write_text("".join(json.dumps(r) + "\n" for r in keep))
    else:  # scramble: an unrelated random walk from the last pre-cut level
        rng = np.random.default_rng(7)
        px = px.sort_values(["ticker", "date"]).reset_index(drop=True)
        fx = fx.sort_values(["pair", "date"]).reset_index(drop=True)
        after_px, after_fx = px["date"].astype(str) > cut, fx["date"].astype(str) > cut
        for t, g in px[after_px].groupby("ticker"):
            last = px[(px["ticker"] == t) & ~after_px]["adj_close"].iloc[-1]
            walk = last * np.exp(np.cumsum(rng.normal(0.0, 0.04, len(g))))
            for col in ("open", "high", "low", "close", "adj_close"):
                px.loc[g.index, col] = walk
        for _, g in fx[after_fx].groupby("pair"):
            last = fx[(fx["pair"] == g["pair"].iloc[0]) & ~after_fx]["rate"].iloc[-1]
            fx.loc[g.index, "rate"] = last * np.exp(np.cumsum(rng.normal(0.0, 0.02, len(g))))
    px.to_parquet(dst / "prices_daily.parquet", index=False)
    fx.to_parquet(dst / "fx_daily.parquet", index=False)
    return dst


@pytest.fixture(scope="module")
def cuts(snapshot_dir) -> list[str]:
    state = build_state(Settings(snapshot_dir=snapshot_dir, llm_mode="fake", app_mode="historical"), db_path=":memory:")
    days = state.gw.trading_days(START)
    return [str(days[k].date()) for k in CUT_OFFSETS]


@pytest.fixture(scope="module")
def full_runs(snapshot_dir):
    return {agents: _simulate(snapshot_dir, None, agents) for agents in (False, True)}


@pytest.mark.parametrize("agents", [False, True], ids=["engine", "agents"])
@pytest.mark.parametrize("how", ["delete", "scramble"])
@pytest.mark.parametrize("k", range(len(CUT_OFFSETS)))
def test_no_peeking(snapshot_dir, tmp_path, full_runs, cuts, agents, how, k):
    cut = cuts[k]
    altered = _rewrite(snapshot_dir, tmp_path / f"{how}_{cut}", cut, how)
    other = _simulate(altered, cut if how == "delete" else None, agents)
    full, alt = _trace(full_runs[agents], cut), _trace(other, cut)
    assert len(full) > 20 and any('"clock.tick"' in e for e in full)
    kinds = {json.loads(e)["type"] for e in full}
    assert {"order.filled", "decision.made", "clock.tick"} <= kinds
    assert "calc.result" in kinds            # the forecast is part of what must not change
    if how == "scramble":   # the scramble must really change what happens AFTER t, or this proves nothing
        assert _trace(full_runs[agents], "9999") != _trace(other, "9999")
    first_diff = next((i for i, (a, b) in enumerate(zip(full, alt, strict=False)) if a != b), None)
    assert first_diff is None and len(full) == len(alt), (
        f"future data changed the past ({how} after {cut}): first difference at event {first_diff}\n"
        f"full:    {full[first_diff] if first_diff is not None else '-'}\n"
        f"altered: {alt[first_diff] if first_diff is not None else '-'}")


def test_a_leaky_gateway_is_caught(snapshot_dir, tmp_path, full_runs, cuts, monkeypatch):
    """Prove the test has teeth: let the gateway ignore as_of, and the comparison must fail."""
    real = DataGateway.prices

    def leaky(self, tickers=None, start=None, end=None, caller="unknown"):
        df = self._prices_gbp                   # BUG on purpose: no as_of cut
        if start is not None:
            df = df.loc[pd.Timestamp(start):]
        return df[tickers] if tickers is not None else df

    cut = cuts[1]
    altered = _rewrite(snapshot_dir, tmp_path / "scramble_leak", cut, "scramble")
    monkeypatch.setattr(DataGateway, "prices", leaky)
    leaked_full = _trace(_simulate(snapshot_dir, None, False), cut)
    leaked_alt = _trace(_simulate(altered, None, False), cut)
    monkeypatch.setattr(DataGateway, "prices", real)
    assert leaked_full != leaked_alt        # with a leak, scrambling the future DOES change the past
