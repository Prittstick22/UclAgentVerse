# 03 · How it works

## 1. User journey

1. **Landing.** Choose "Historical demo · As of 7 Nov 2025" or "Current markets · Paper portfolio".
2. **Quiz** (about 8 questions, plain English, £ examples such as "If £10,000 fell to £8,000, would that stop you reaching your goal?").
   - `POST /api/profile/quiz` → profile + mandate.
   - Conflicting answers produce one follow-up question.
3. **Mandate review.** Editable ranges, caps, exclusions, cadence. The user selects **Build my portfolio**.
4. **Agent workspace.** The lead fills the canvas, then moves left as specialists open on the right (max 3 visible, others in a rail). It's a live tree with depth, refused spawns and tool calls.
5. **Proposal:**
   - recommended portfolio + 2 alternatives
   - holding purposes, "why this rather than that"
   - correlation lattice, backtest on pre-start data (labelled)
   - gate strip (Evidence · Numbers · Critic · Compliance · QA), uncertainties
   - Approve
6. **Home ("while you were away"):** status pill, last review, holdings with P&L, recent rebalances, digest, waiting decision.
7. **Timeline (historical):** play/pause/speed and a scrubber. NAV vs benchmarks, weights stacked area, markers for each agent run (shape = trigger kind, colour = maintain/adjust). Clicking a marker replays the run.
8. **Decision card:** headline, the change in £, risk warning, gate strip, Approve / Keep / Why?
9. **Chat:** ask anything; answers cite evidence chips.

## 2. Modes

| | Historical | Live |
|---|---|---|
| Clock | `SimClock`, starts 2025-11-07, steps trading days | `LiveClock`, real time |
| Data | Snapshot in the image, revealed up to `as_of` | Snapshot + daily EOD top-up + optional display quotes |
| Web search | Blocked | Gemini grounding allowed inside investigations |
| Portfolio | Fictional historical portfolio | Persistent paper portfolio |
| Memory | `historical` namespace | `live` namespace; demo outcomes never leak in |
| Approvals | Simulated by policy in the overnight batch (labelled); manual for the demo hero decision | Manual |
| Label | "Historical demo · As of {date}" | "Current markets · Paper portfolio" |

## 3. The day loop (historical)

```python
for day in calendar.trading_days("2025-11-07", end):
    clock.set(day)                                   # act at the close (16:30 London)
    ledger.fill_pending(gw.prices(as_of=day))        # yesterday's decisions fill at today's close (+costs)
    ledger.mark_to_market(gw.prices(as_of=day)); ledger.accrue_fund_fees(day)
    if calendar.is_first_trading_day_of_month(day): ledger.deposit(contribution)
    risk = engine.risk.snapshot(gw, as_of=day)       # rolling Ledoit-Wolf cov + corr
    outlook = engine.forecast(gw, as_of=day, horizon=10)  # 2-week estimate from data <= day only
    hits = monitors.evaluate(day, ledger, risk, gw)  # drift, cap, price move, NAV drop, news, corr regime
    hits = cooldowns.filter(hits, day)               # 1 ad hoc run per holding per 5 days; fold into review if due within 2 days
    if schedule.is_review_day(day) or hits:
        run = supervisor.start(kind=hits.kind or "review", trigger=hits.describe(), as_of=day)
        if run.decision.action == "adjust" and run.gate.passed and approvals.allows(run.proposal):
            ledger.queue(run.proposal.orders)
    benchmarks.step(day)
    events.emit("clock.tick", nav=..., weights=..., benchmarks=...)
```

- **Decide at day t's close, fill at day t+1's close.** No same-bar look-ahead.
- **"Optimises daily" means the target is recomputed daily, but trades only happen outside the bands.** A review doesn't have to trade; most end in "maintain".
- **Every run records its trigger in words,** e.g. "Started because NVDA fell 6.1% on 2026-05-21 (price-move trigger)".

## 4. Triggers and responses

| Trigger | Fires when | Response |
|---|---|---|
| Scheduled review | Every 10 trading days (`review_every_n_days`, 5 = weekly) | Review run; usually maintain |
| Drift | Asset class or holding ≥ 5 percentage points from target | Rebalance run |
| Cap breach | Holding over its cap after price moves | Rebalance run |
| Price move | Holding ≥ 5% in a day or ≥ 10% since the last review | Trigger run: investigate why, then maintain or adjust |
| NAV drop | NAV ≥ 5% below the last review | Trigger run |
| News | Flash relevance ≥ 0.7 for a holding | Trigger run |
| Correlation regime | Average pairwise correlation up > 0.15 vs 6 months earlier | Noted at the next review; never trades on its own |

- Same-day price-move triggers across many holdings are grouped into one portfolio-level run.
- Price moves cause investigations, not automatic trades.

## 5. Agent runs (detail in 05-agent-system)

- Every run is a **tree**. The Argon lead decides which sub-agents to spawn, starting from a default plan for its run kind.
- The supervisor (code) enforces max depth 2, headcount, 3 in parallel, a token budget and one revision loop.
- Outputs go through the **assurance gate**:
  1. injection guard
  2. evidence checker
  3. numbers + mandate checks (code)
  4. critic
  5. compliance
  6. QA
  7. user approval
  8. pre-execution revalidation (code)
- "Maintain" outcomes get a light gate.

## 6. Notifications

- **Adjust** → `notification(kind=decision)` + decision card.
- **Maintain** → digest line, no push.
- **Data outage** → status "Monitoring degraded" + `notification(kind=coverage)`.
- **Headline metric:** "This year: X reviews, Y checks, Z decisions asked of you."

## 7. Replay vs re-run

- **Replay** reads recorded events (`GET /api/runs/{id}/events`). It's instant, free and deterministic. The public demo uses this.
- **Re-run** executes the simulator again with the LLM cache. Cached calls are free; changed prompts call Gemini.
