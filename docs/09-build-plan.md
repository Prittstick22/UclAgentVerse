# 09 · Build plan

Times are London, Sat 7 → Sun 8 Nov 2026. **Everyone stays up. Everything working by 09:00. Submit by 12:20 (deadline 12:30).**

**End goal:** one public link with everything running (demo + live mode), where **the demo never waits on an API call**. The demo replays the recorded 4-month agent run; live mode reads cached data and runs agents asynchronously (#78).

## Milestones (GitHub milestones)

| Milestone | By | Done when |
|---|---|---|
| **M0 Setup** | **00:00** | Everyone runs backend + frontend locally; Gemini pinged; provider keys verified and sent to Jin; real snapshot download started |
| **M1 Spine end to end** | **02:30** | Quiz → mandate → agent construction streamed to the UI → optimiser + checks → approve → ledger; deterministic sim with forecast + benchmarks; home, P&L, lattice, timeline on the real API; **config frozen (tag `eval-freeze`)** |
| **M2 DONE: live link** | **09:00** | Recorded 4-month agent run + no-agents baseline; full gate; decision cards; replay; live mode; controls on film; eval table; **deployed link works for demo + live, with no API waits**; all `mvp` issues merged |
| **M3 Video, deck, submit** | **12:20** | Video recorded from the link; deck with evidence; README; data sources; rehearsal; submitted |

## Timeline (everyone awake)

| Time | Dev (agents, APIs) | Cem (engine, sim) | Jin (data, API, deploy) | Mo (frontend) |
|---|---|---|---|---|
| **23:00–00:00** | #27 Gemini ping · #3/#54 keys · #55 `check_providers.py` → keys to Jin | #15 risk · #16 optimiser · #73 forecast (start) | #5 catalogue · #6 real prices/FX download (with Dev's keys) · #62 data sources | #40 shell · #41 quiz + mandate (mock) |
| **00:00** | **Switch 1: real snapshot posted (Jin)** | | | |
| **00:00–01:30** | #60 finance kit · #28 agent loop · #29 tools | #73 forecast → optimiser · #17 checker · #18 ledger | #7 news/filings (Jul–Nov 2026, hero events) · #9 runs API · #8 mandate API | #42 agent workspace · #44 home + P&L · #45 lattice |
| **01:30–02:30** | #30 construction plan → **switch 2: real fixtures** · #31 review/trigger plans · #20 benchmarks | #19 day loop + monitors · #22 sim ↔ agents + `--no-agents` · #21 portfolio API | #10 notifications/status · #12 public-demo safety · #78 no-API-wait design | #43 proposal · #46 timeline |
| **02:30** | **M1 integration on one machine · switch 3: `eval-freeze` tag** · 2-week agent slice, timed | | | |
| **03:00–04:15** | **Launch the 4-month agent run (~1 h) on the batch laptop**, then `--no-agents` baseline · meanwhile #32 gate · #33 guard | #72 no-peeking test · #23 approve/decline · #24 eval script | **Deploy dry run:** droplet + HTTPS + current main on the real link | #48 decision card · #49 rebalances + benchmarks |
| **04:15** | **Switch 4: recorded run posted** (`runs/year.sqlite`, `runs/no_agents.sqlite`) | | | |
| **04:15–06:30** | #61 finance-kit run · #34 explainer · #35 chat (feature) | Eval numbers from the recorded runs · #25 exposure (feature) | #11 live mode (cron, cache) · #78 replay from the recorded run · #13 bake in runs | #50 replay (feature) · #47 gate strip (feature) · polish |
| **06:30** | **Second deploy** with recorded runs; smoke test the demo + live on the link | | | |
| **07:00** | **Feature freeze:** unstarted `feature` issues are dropped; bug fixes only | | | |
| **07:00–08:30** | Bug fixes · #39 deck draft | Bug fixes · #68 compliance checklist (start) | Fixes + **final deploy 08:00** · #70 README | Fixes · UI polish |
| **08:30–09:00** | **Full smoke test on the link: demo (no keys needed) + live mode. M2 DONE** | | | |
| 09:00–11:00 | #39 deck · #69 Q&A cheat sheet | #68 checklist · eval slide | #66 who-it-helps stats · README links | #52 record video from the link |
| 11:00–12:00 | Rehearsal (4 min + 2 min Q&A) · final checks | | | |
| **12:20** | **Submit** (deadline 12:30) | | | |

**Batch laptop:** whoever runs the 03:00 agent run keeps that machine plugged in, awake (sleep disabled) and online until ~04:15. Decide at the 02:30 integration.

## Labels: `mvp` vs `feature`

Every issue is tagged `mvp` (the minimum demo that works end to end: quiz → agent build → checks → approve → year simulation → home/P&L/lattice/timeline/benchmarks → eval + finance kit → deck/video/README) or `feature` (additional). Work `mvp` first: `gh issue list --label owner:<you> --label mvp`. At 07:00, any `feature` issue not started is dropped.

## If behind (cut in this order)

1. Tier 3 entirely
2. Agent-designed monitors → keep fixed monitors only
3. Chat → keep the "Why?" replay
4. Live mode → a 30-second clip of the clock switch
5. Two alternatives → recommended only
6. Never cut: the gate strip on proposals, replay, benchmarks, controls

## Agent-run checklist (03:00)

- [ ] `config/*.yaml` frozen and tagged `eval-freeze`
- [ ] 2-week slice ran in under 10 min; extrapolated to under 1.5 h for the 4-month window
- [ ] LLM cache on; Gemini budget alert set
- [ ] `python -m app.sim.runner --start 2026-07-07 --end <last> --agents --approvals batch_policy --record runs/year.sqlite`
- [ ] Then `python -m app.sim.runner --start 2026-07-07 --end <last> --no-agents --record runs/no_agents.sqlite`
- [ ] Post both files on the board (switch 4) with sha256
