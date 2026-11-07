# 09 · Build plan

Times are London, Sat 7 → Sun 8 Nov 2026. **Feature freeze 09:00 · demo + deck done 11:00 · submit 12:20 · hard deadline 13:00.**

## Milestones (GitHub milestones)

| Milestone | Due | Done when |
|---|---|---|
| **M0 Setup** | Sat 22:30 | Everyone runs backend + frontend locally; synthetic snapshot; EODHD coverage tested; Argon key pinged; hello-world deployed to the DigitalOcean droplet |
| **M1 Spine (Tier 1)** | Sun 03:00 | Quiz → mandate → agent construction run streamed to the UI → optimiser + checks → approve → ledger; deterministic full-year sim + benchmarks; home, P&L, lattice, timeline on real API |
| **M2 Differentiator (Tier 2) + freeze** | Sun 09:00 | Overnight agent batch recorded; replay; full gate + badges; alternatives; decision cards; rebalances; chat; monitors; live mode; 4 controls; eval table |
| **M3 Demo + submit** | Sun 12:20 | Video recorded from the hosted link; deck with eval numbers; submission done |

## Timeline

| Time | Dev (agents) | Cem (engine/sim) | Jin (data/platform) | Mo (frontend) |
|---|---|---|---|---|
| 20:45–22:30 | Ping Argon; LLM wrapper + cache + fake mode; supervisor skeleton with limits | Risk + correlation; optimiser v1 with tests | Synthetic snapshot; gateway; events + SSE; EODHD free-plan coverage test; DigitalOcean droplet + hello-world deploy | App shell, router, mode badge; quiz + mandate screens on mock |
| 22:30–03:00 | Roles + prompts (lead, scouts, risk, stock); tools registry; construction plan end to end; gate skeleton (numbers + mandate via Cem) | Checker; ledger; metrics; deterministic sim loop; benchmarks; monitors + cooldowns | Real snapshot fetch (EODHD/Finnhub/EDGAR); quiz scoring; all API routes on real code | Agent workspace tree from SSE; proposal screen; home + P&L; correlation lattice; timeline |
| **03:00** | **Integration 1 (M1).** Run a 1-month agent slice, time it, fix. **Launch the full-year agent batch** (`LLM_MODE=live`, batch approvals). Freeze config | | | |
| 03:00–06:00 | Sleep shift / monitor the batch | Batch watch → eval numbers script | Sleep shift | Sleep shift |
| 06:00–09:00 | Evidence checker, critic, compliance, QA, guard; chat; monitor designer | Exposure tool; rebalances + pnl endpoints; eval table | Live mode (EOD task, Scheduler), freshness, notifications; deploy the recorded run | Gate strip + badges; decision card; replay; chat; rebalances; benchmarks |
| **09:00** | **Feature freeze.** Bake in the recorded run, deploy, smoke test the public link | | | |
| 09:00–11:00 | Deck + script | Eval slide + numbers check | Deploy fixes only | Record video (2 takes) + edit |
| 11:00–12:20 | Final review, submit by 12:20 | | | |

## If behind (cut in this order)

1. Tier 3 entirely
2. Agent-designed monitors → keep fixed monitors only
3. Chat → keep the "Why?" replay
4. Live mode → a 30-second clip of the clock switch
5. Two alternatives → recommended only
6. Never cut: the gate strip on proposals, replay, benchmarks, controls

## Overnight batch checklist (03:00)

- [ ] `config/*.yaml` frozen and committed (tag `eval-freeze`)
- [ ] 1-month slice ran in under 15 min; extrapolated to < 3 h for the year
- [ ] LLM cache on; Gemini budget alert set
- [ ] `python -m app.sim.runner --start 2025-11-07 --end <last> --agents --approvals batch_policy --record runs/year.sqlite`
- [ ] Someone awake checks progress every 30 min (`GET /api/sim/status`)
