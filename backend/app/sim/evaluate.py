"""Evaluation for the deck (#24). Owner: Cem. Spec: docs/10-evaluation.md.

    python -m app.sim.evaluate --record runs/year.sqlite \\
        [--record ours_no_agents=runs/no_agents.sqlite] [--record ours_no_forecast=runs/no_forecast.sqlite] \\
        --out eval/

The first --record is `ours` and supplies the four benchmarks; each extra `label=path` adds its `ours` as a row.
Writes eval/metrics.json, eval/table.md (paste into the deck) and eval/nav.png (eval/nav.svg without matplotlib).
GET /api/benchmarks serves the same numbers via `benchmarks_payload()`. Every number is simulated, not a forecast.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from app.config import params
from app.core.db import DB
from app.engine.metrics import Metrics, compute
from app.sim.runner import RESULTS_NS

BENCHMARKS = ("buy_and_hold", "quarterly_rebalance", "global_etf", "mechanical_5pct")
LABELS = {
    "ours": "Ours (Gemini agents + engine)", "ours_no_agents": "Ours, engine only (no agents)",
    "ours_no_forecast": "Ours, no 2-week forecast", "buy_and_hold": "Buy and hold",
    "quarterly_rebalance": "Quarterly rebalance", "global_etf": "One global ETF (VWRP)",
    "mechanical_5pct": "Mechanical 5% rebalance",
}
CAVEATS = [
    "Four months is one short path: not statistically significant.",
    "Simulated backtest on past prices, not live performance and not a forecast.",
    "Approvals in the recorded run were made by the batch policy, not by a person.",
    "Synthetic items are labelled as synthetic.",
    "Trading costs (0.10%, +0.15% FX on US shares) are assumptions.",
    "Current ETF holdings are used as a proxy for look-through exposure.",
    "Turnover is one-way, excludes the initial build from cash, and includes investing monthly contributions.",
]


def load_results(db: DB) -> dict | None:
    raw = db.get(RESULTS_NS, "latest")
    return json.loads(raw) if raw else None


def strategy_metrics(strategy: dict) -> Metrics:
    s = pd.Series({p["date"]: p["nav_gbp"] for p in strategy["series"]}, dtype=float)
    flows = pd.Series(strategy.get("flows", {}), dtype=float)
    m = compute(s, flows, costs_gbp=strategy.get("costs_gbp", 0.0), trades=strategy.get("trades", 0))
    avg_nav = float(s.mean()) if len(s) else 0.0
    m.turnover = round(strategy.get("traded_gbp", 0.0) / 2 / avg_nav, 4) if avg_nav else 0.0
    return m


def benchmarks_payload(db: DB) -> dict:
    """Contract of GET /api/benchmarks (docs/04): {series, metrics, periods}. Empty until a replay finishes."""
    res = load_results(db)
    held_out = params()["periods"]["held_out"]
    periods = {"development": params()["periods"]["development"], "held_out": [held_out[0], held_out[1]]}
    if not res:
        return {"series": {}, "metrics": {}, "periods": periods}
    periods["held_out"] = [res["start"], res["end"]]
    strategies = res["strategies"]
    return {"series": {n: st["series"] for n, st in strategies.items()},
            "metrics": {n: strategy_metrics(st).model_dump() for n, st in strategies.items()},
            "periods": periods}


def event_counts(db: DB, res: dict) -> dict:
    """The 'ours only' numbers: what the system did and how often it asked the user."""
    def n(sql: str, *a) -> int:
        return int(db.execute(sql, a)[0][0])

    runs = res.get("runs", [])
    gate_fails = sum(1 for (raw,) in db.execute("SELECT json FROM events WHERE type='gate.verdict'")
                     if json.loads(raw).get("payload", {}).get("status") == "fail")
    evidence: set[str] = set()
    for (raw,) in db.execute("SELECT json FROM events"):
        evidence.update(json.loads(raw).get("evidence_ids") or [])
    return {
        "reviews": sum(r["kind"] == "review" for r in runs),
        "trigger_runs": sum(r["kind"] not in ("review", "construction") for r in runs),
        "maintain": sum(r["action"] == "maintain" for r in runs),
        "adjust": sum(r["action"] in ("adjust", "approved") for r in runs),
        "decisions_asked": n("SELECT COUNT(*) FROM events WHERE type='approval.requested'"),
        "auto_approved": n("SELECT COUNT(*) FROM events WHERE type='approval.decided' AND json LIKE '%batch_policy%'"),
        "gate_failures": gate_fails,
        "quarantined": n("SELECT COUNT(*) FROM events WHERE type='content.quarantined'"),
        "refused_spawns": n("SELECT COUNT(*) FROM events WHERE type='agent.spawn_denied'"),
        "monitor_hits": n("SELECT COUNT(*) FROM events WHERE type='monitor.fired'"),
        "agent_runs": n("SELECT COUNT(*) FROM events WHERE type='run.started'"),
        "events": n("SELECT COUNT(*) FROM events"),
        "evidence_items": len(evidence),
        "triggers_by_kind": res.get("trigger_counts", {}),
    }


def evaluate(records: dict[str, Path], out: Path) -> dict:
    """records: {label: sqlite path}, first one is 'ours' and provides the benchmarks."""
    out.mkdir(parents=True, exist_ok=True)
    rows: dict[str, dict] = {}
    meta: dict = {}
    counts: dict = {}
    for i, (label, path) in enumerate(records.items()):
        if not Path(path).exists():
            raise FileNotFoundError(f"No recorded run at {path}")
        db = DB(path)
        res = load_results(db)
        if res is None:
            raise ValueError(f"{path} has no finished replay (run the simulator with --record first)")
        rows[label] = {"strategy": res["strategies"]["ours"], "run": {k: res[k] for k in
                       ("start", "end", "agents", "approvals", "profile", "lambda_return", "data_source")}
                       | {"forecast": res.get("forecast", True)}}
        if i == 0:
            meta = rows[label]["run"]
            counts = event_counts(db, res)
            for b in BENCHMARKS:
                if b in res["strategies"]:
                    rows[b] = {"strategy": res["strategies"][b], "run": rows[label]["run"]}
        elif (res["start"], res["end"]) != (meta["start"], meta["end"]):
            raise ValueError(f"{label} covers {res['start']} to {res['end']}, not {meta['start']} to {meta['end']}")
    metrics = {k: strategy_metrics(v["strategy"]) for k, v in rows.items()}
    finals = {k: v["strategy"]["series"][-1]["nav_gbp"] if v["strategy"]["series"] else 0.0 for k, v in rows.items()}
    result = {"window": [meta["start"], meta["end"]], "run": meta, "label": "simulated, not a forecast",
              "metrics": {k: m.model_dump() for k, m in metrics.items()}, "final_nav_gbp": finals,
              "ours_only": counts, "caveats": CAVEATS, "ablation_runs": {k: v["run"] for k, v in rows.items()
                                                                          if k not in BENCHMARKS}}
    (out / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (out / "table.md").write_text(_table(result, metrics, finals), encoding="utf-8")
    result["chart"] = str(_chart({k: v["strategy"]["series"] for k, v in rows.items()}, out, meta))
    return result


def _pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


def _table(result: dict, metrics: dict[str, Metrics], finals: dict[str, float]) -> str:
    run, c = result["run"], result["ours_only"]
    lines = [
        f"### Simulated results, {run['start']} to {run['end']} (held out, after the model's knowledge cutoff)",
        "",
        (f"Profile: {run['profile']} | £{params()['sim']['capital_gbp']:,} start + "
        f"£{params()['sim']['monthly_contribution_gbp']}/month | data: {run['data_source']} | "
        f"approvals: {run['approvals']} | forecast weight lambda = {run['lambda_return']}. **Simulated, not a forecast.**"),
        "",
        "| Strategy | Return (TWR) | Volatility (ann.) | Max drawdown | Sharpe (rf = 0) | Turnover | Costs | Trades | Final value |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for k, m in metrics.items():
        lines.append(f"| {LABELS.get(k, k)} | {_pct(m.total_return)} | {m.vol_annual * 100:.1f}% | "
                     f"{_pct(m.max_drawdown)} | {m.sharpe:.2f} | {m.turnover * 100:.1f}% | £{m.costs_gbp:,.2f} | "
                     f"{m.trades} | £{finals[k]:,.2f} |")
    lines += [
        "",
        ("**What the system did (ours):** "
        f"{c['reviews']} scheduled reviews, {c['trigger_runs']} trigger runs, {c['monitor_hits']} monitor alerts; "
        f"{c['maintain']} maintain vs {c['adjust']} adjust; asked you to decide **{c['decisions_asked']}** times "
        f"({c['auto_approved']} auto-approved by the batch policy); {c['gate_failures']} gate failures caught; "
        f"{c['quarantined']} items quarantined; {c['refused_spawns']} agent spawns refused."),
        "",
        (f"Every decision traceable: {c['events']:,} events, {c['evidence_items']:,} evidence items; all numbers "
        "recomputed by code."),
        "",
        "**Caveats**",
        *[f"- {x}" for x in result["caveats"]],
        "",
    ]
    return "\n".join(lines)


def _chart(series: dict[str, list[dict]], out: Path, meta: dict) -> Path:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return _svg(series, out / "nav.svg", meta)
    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=150)
    for name, pts in series.items():
        if not pts:
            continue
        x = pd.to_datetime([p["date"] for p in pts])
        ax.plot(x, [p["nav_gbp"] for p in pts], label=LABELS.get(name, name),
                linewidth=2.6 if name == "ours" else 1.4, alpha=1.0 if name.startswith("ours") else 0.8)
    ax.set_title(f"Portfolio value (£), {meta['start']} to {meta['end']}. Simulated, not a forecast")
    ax.set_ylabel("£")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    path = out / "nav.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def _svg(series: dict[str, list[dict]], path: Path, meta: dict) -> Path:
    """Dependency-free fallback chart."""
    w, h, pad = 900, 460, 50
    pts_all = [p for pts in series.values() for p in pts]
    if not pts_all:
        path.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
        return path
    dates = sorted({p["date"] for p in pts_all})
    lo, hi = min(p["nav_gbp"] for p in pts_all), max(p["nav_gbp"] for p in pts_all)
    span = (hi - lo) or 1.0
    xi = {d: pad + i * (w - 2 * pad) / max(len(dates) - 1, 1) for i, d in enumerate(dates)}
    colours = ["#1b6ef3", "#7b3fe4", "#0f9d58", "#f4b400", "#db4437", "#00acc1", "#795548"]
    parts = [(f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' font-family='sans-serif' "
             f"font-size='12'><rect width='100%' height='100%' fill='white'/>"),
             (f"<text x='{pad}' y='24' font-size='14'>Portfolio value (£), {meta['start']} to {meta['end']}. "
             "Simulated, not a forecast</text>")]
    for i, (name, pts) in enumerate(series.items()):
        if not pts:
            continue
        poly = " ".join(f"{xi[p['date']]:.1f},{h - pad - (p['nav_gbp'] - lo) / span * (h - 2 * pad):.1f}" for p in pts)
        col = colours[i % len(colours)]
        parts.append(f"<polyline fill='none' stroke='{col}' stroke-width='{3 if name == 'ours' else 1.5}' "
                     f"points='{poly}'/>")
        parts.append(f"<text x='{w - 260}' y='{50 + 16 * i}' fill='{col}'>{LABELS.get(name, name)}</text>")
    parts.append(f"<text x='{pad}' y='{h - 15}'>£{lo:,.0f} to £{hi:,.0f}</text></svg>")
    path.write_text("".join(parts), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> None:  # pragma: no cover
    p = argparse.ArgumentParser(description="Evaluation table + NAV chart for the deck (#24)")
    p.add_argument("--record", action="append", required=True,
                   help="SQLite from `python -m app.sim.runner --record`; first = ours, extra as label=path")
    p.add_argument("--out", default="eval")
    a = p.parse_args(argv)
    records: dict[str, Path] = {}
    for i, r in enumerate(a.record):
        label, _, path = r.partition("=") if "=" in r else ("ours" if i == 0 else Path(r).stem, "", r)
        records[label if i else "ours"] = Path(path)
    res = evaluate(records, Path(a.out))
    # ASCII on the console (a Windows console or redirect may not encode the pound sign); the files are UTF-8
    print(f"Wrote {a.out}/metrics.json, {a.out}/table.md and {res['chart']}")
    for k, m in res["metrics"].items():
        print(f"  {k:22s} return {m['total_return'] * 100:+6.2f}%  max drawdown {m['max_drawdown'] * 100:+6.2f}%  "
              f"final GBP {res['final_nav_gbp'][k]:,.2f}")


if __name__ == "__main__":  # pragma: no cover
    main()
