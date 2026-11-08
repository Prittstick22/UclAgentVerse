"""#61: the organisers' finance-kit adapter (offline; no kit code imported)."""
import json
import subprocess
import sys
import time
from pathlib import Path

from app.eval import finance_kit_adapter as fk

BACKEND = Path(__file__).resolve().parent.parent


def step(prices, shares=0, cash=1_000_000, fee=100):
    return {"request_id": "r", "case_id": "c", "task": "market_step",
            "input": {"history": [{"date": f"d{i}", "price_pence": p} for i, p in enumerate(prices)],
                      "cash_pence": cash, "shares": shares, "fee_pence": fee, "slippage_bps": 10}}


def test_invests_at_the_start_and_holds_in_calm_markets():
    assert fk.solve(step([1000]))["action"] == "buy"
    calm = [1000 + (i % 3) for i in range(80)]
    assert fk.solve(step(calm, shares=10))["action"] == "hold"


def test_steps_aside_on_a_deep_drawdown():
    prices = [1000] * 30 + [1000 - 10 * i for i in range(1, 21)]   # -20% from the recent peak
    assert fk.solve(step(prices, shares=10))["action"] == "sell"


def test_steps_aside_when_volatility_spikes():
    calm = [1000 + (1 if i % 2 else -1) for i in range(60)]
    wild = calm + [1000 + (60 if i % 2 else -60) for i in range(20)]
    assert fk.solve(step(wild, shares=10))["action"] == "sell"


def test_reenters_only_when_calm_and_above_average():
    falling = [1000] * 30 + [1000 - 10 * i for i in range(1, 21)]
    assert fk.solve(step(falling))["action"] == "hold"                      # still stressed: stay in cash
    recovered = [800 + i for i in range(80)]
    assert fk.solve(step(recovered))["action"] == "buy"


def test_never_buys_without_enough_cash_and_rejects_bad_input():
    assert fk.solve(step([1000, 1001], cash=500))["action"] == "hold"
    assert fk.solve(step([1000, -5]))["error"] == "invalid_input"


def test_uses_only_the_history_it_was_given():
    path = [1000 + (i % 7) for i in range(100)]
    for n in (5, 50, 100):
        a = fk.solve(step(path[:n], shares=10))
        b = fk.solve(step(path[:n] + [], shares=10))
        assert a == b                                     # same visible history -> same answer (deterministic)


def test_other_tasks_are_unsupported():
    assert fk.solve({"request_id": "x", "task": "cashflow", "input": {}}) == {"error": "unsupported_task"}


def test_fast_enough_for_the_runner():
    req = step([1000 + (i % 11) for i in range(500)], shares=10)
    t = time.perf_counter()
    for _ in range(200):
        fk.solve(req)
    assert (time.perf_counter() - t) / 200 < 0.02            # < 20 ms per answer (runner allows 10 s)


def test_protocol_over_stdin_stdout():
    lines = [json.dumps(step([1000])), json.dumps({"request_id": "z", "task": "transactions", "input": {}}), ""]
    out = subprocess.run([sys.executable, "-m", "app.eval.finance_kit_adapter"], input="\n".join(lines),
                         capture_output=True, text=True, cwd=BACKEND, timeout=60)
    replies = [json.loads(x) for x in out.stdout.strip().splitlines()]
    assert replies == [{"request_id": "r", "output": {"action": "buy"}},
                       {"request_id": "z", "output": {"error": "unsupported_task"}}]
