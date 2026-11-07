# 09 · Build plan

Times are London, Sat 7 → Sun 8 Nov 2026. **Everyone stays up. Everything working by 09:00. Submit by 12:20 (deadline 12:30).**

**End goal:** one public link with everything running (demo + live mode), where **the demo never waits on an API call**. The demo replays the recorded 4-month agent run; live mode reads cached data and runs agents asynchronously (#78).

## Milestones (GitHub milestones)

| Milestone | By | Done when |
|---|---|---|
| **M0 Setup** | **00:00** | Everyone runs backend + frontend locally; Gemini pinged; provider keys verified and sent to Jin; real snapshot download started |
| **M1 Spine end to end** | **02:30** | Quiz → mandate → agent construction streamed to the UI → optimiser + checks → approve → ledger; deterministic sim with forecast + benchmarks; home, P&L, lattice, timeline on the real API; **config frozen (tag `eval-freeze`)** |
| **M2 DONE: live link** | **09:00** | Recorded 4-month agent run + no-agents baseline; full gate; decision cards; replay; live mode; controls on film; eval table; **deployed link works for demo + live, with no API waits**; all `mvp` issues merged |
| **M3 Video, deck, submit** | **12:20** | Video (rough cut 07:30, final 10:30) and deck (draft 10:30, PDF 11:00) built in parallel since 02:30; README; data sources; rehearsal; submitted |

## Timeline (everyone awake)

The demo video and the deck are built **in parallel** with the code (editing takes long), not after 09:00. Dev owns all deploys.

| Time | Dev (agents, APIs, **deploys**, pitch content) | Cem (engine, sim, eval) | Jin (data, API, **deck slides**) | Mo (frontend, **video**) |
|---|---|---|---|---|
| **23:00–00:00** | #27 Gemini ping · #3/#54 keys · #55 `check_providers.py` → keys to Jin | #15 risk · #16 optimiser · #73 forecast (start) | #5 catalogue · #6 real prices/FX download · #62 data sources | #40 shell · #41 quiz + mandate (mock) |
| **00:00** | **Switch 1: real snapshot posted (Jin)** | | | |
| **00:00–01:30** | #60 finance kit · #28 agent loop · #29 tools | #73 forecast → optimiser · #17 checker · #18 ledger | #7 news/filings (hero events in the window) · #9 runs API · #8 mandate API | #42 agent workspace · #44 home + P&L · #45 lattice |
| **01:30–02:30** | #30 construction plan → **switch 2: real fixtures** · #31 review/trigger plans · #20 benchmarks · #39 story + slide text (batch 1) | #19 day loop + `--no-agents` · #22 sim ↔ agents · #21 portfolio API | #10 notifications/status · #12 public-demo safety · #78 no-API-wait | #43 proposal · #46 timeline · **#82 video shot list (by 02:30)** |
| **02:30** | **M1 integration · switch 3: `eval-freeze` tag** · 2-week agent slice, timed | | | |
| **03:00–04:15** | **Launch the 4-month agent run (~1 h)** + baseline · **#4 deploy dry run** (droplet, HTTPS, current main) | #72 no-peeking test · #23 approve/decline · #24 eval script | #11 live mode (cache, cron) · **#84 deck: template + slides batch 1** | #48 decision card · #49 rebalances + benchmarks · #82 placeholder clips |
| **04:15** | **Switch 4: recorded runs posted** | | | |
| **04:15–06:30** | #61 finance-kit run · #32 gate · #33 guard · #34 explainer · #39 slide text batch 2 (controls, traceability) | Eval numbers from the recorded runs · #68 checklist (start) | #78 replay from the recorded run · #84 deck batch 2 · #66 who-it-helps stats | #50 replay · #47 gate strip · polish |
| **06:30** | **#13 second deploy** with recorded runs · smoke test | | | **#83 capture every shot from the link** |
| **07:00** | **Feature freeze:** unstarted `feature` issues dropped; bug fixes only | | | |
| **07:00–08:30** | Bug fixes · **08:00 final deploy** · voice-over 08:00–08:30 | Bug fixes · eval numbers → Dev/Jin by 08:30 | Fixes · #70 README · #84 deck screenshots | **07:30 rough cut** · fixes |
| **08:30–09:00** | **Full smoke test on the link: demo (no keys) + live. M2 DONE** | | | |
| 09:00–10:30 | #39 final slide text · #69 Q&A cheat sheet | #68 checklist across deck/video/README/UI | #84 eval slide + final screenshots · **10:30 deck draft** | #83 re-capture changed shots · **10:30 final video** |
| 10:30–12:00 | Review deck + video together · **11:00 deck PDF** · rehearsal ×2 (4 min + 2 min Q&A) | | | |
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
