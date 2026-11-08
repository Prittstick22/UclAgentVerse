# Dev: what to do now (Codex handoff, Sun 8 Nov 2026)

Any agent can pick this up (Claude Code, Codex/GPT, Gemini CLI, Cursor), for example while Dev's Claude credits reset. Read `AGENTS.md` first; the team timeline is in `docs/09-build-plan.md`. **Goal: one public link with demo + live mode, everything working by 09:00. The demo never waits on an API call. Submit by 12:20.**

## Resume here: current state (keep this section updated)

**Handed over Sun 8 Nov ~05:15** (Dev's Claude credits ran low; Dev will be back). `main` is clean; **no Dev branches or PRs open**, and nothing is half-done. The one open PR is Mo's #132 (holding logos), not Dev's.

**Model note:** the session switched Opus 5.5 → Sonnet 5.5 at ~05:00 and **back to Opus 5.5** at ~05:10. Use whatever attribution line your own harness gives you. When you post live-run results, say which model produced them.

### Latest: evidence inspection fix active locally (Codex, 8 Nov)

- User authorised bug fixes across the app while Mo continues frontend design. Reproduced the intermittent Inspect evidence errors: 6 distinct missing handlers repeated across the five saved runs (catalogue, four case:*:v1 IDs, proposal:*). The other 33 IDs worked; not an EODHD outage or exhausted tokens.
- Branch `dev/evidence-inspection-fix`: backend resolves catalogue, exact case versions and proposals; earnings/calendar and saved web links also covered. New case saves preserve immutable version records. Future/wrong-mode/missing IDs still return 404; old recordings never substitute another case version. Proposal evidence omits later approval/selection/gate state. Matching Evidence kinds documented and exported in TS; no layout/CSS edits. Board contract-change notice posted on main.
- Validation: all 435 backend tests passed; 12 focused evidence/contract tests passed after final lint cleanup; targeted ruff passed; frontend production build passed. Source recording SHA unchanged. All 39/39 evidence refs returned HTTP 200 through :5173 after restart; audits saved in `backend/runs/smoke/final-ui-20261108T063302Z/evidence-audit-*.json`.
- Restarted ONLY backend to load fix: launcher PID 31388 / server PID 38328 (:8000); fixed frontend preview PID 39564 (:5173) unchanged. Same read-only recording, Sep 1 historical replay, real EODHD snapshot. Zero new model runs, no deployment. Verify PID identity before stopping.
- Publication: PR #137 merged as 4a1d40d after BOTH GitHub CI jobs passed (backend + frontend). Fix is on main and active locally; all 39 UI inspection targets also audited, including nested case/proposal refs. No paid calls or deployment.
- Next: user refreshes VS Code app and retries Inspect evidence. Preserve their control. Do not run paid builds/reviews or extend simulation without instruction. If another link fails, collect its evidence ID/run and diagnose; do not regenerate evidence or relabel synthetic sources. Commit/push status is reported separately when publication finishes.

### Latest: fixed-build final UI retest ready (Codex, 8 Nov ~06:35)

- Follow-up verification: user's subsequent pull reached 2ba7223, which only adds the handover above. GitHub main has no newer application commits than 3c4545c and no open PRs at this check. Running :5173 serves the isolated build's exact JS/CSS asset names (index-Cx2nwKCG.js / index-BkqFSRAS.css); no restart or new run performed. Explain that the handover is our session record, and guide Demo -> Open demo timeline -> Home for holding charts; onboarding is not the main redesigned dashboard.

- Dev requested another shutdown/pull/restart, specifically expecting holding selection charts and improved UI. Stopped only our owned standard backend (38660/41920) and Vite (40592), then fast-forwarded main 98d48a6 -> 3c4545c.
- Incoming changes include frontend overhaul plus backend holding prices, news and live approval opt-in. Read Mo's board notes. Asset clicks now select Performance and GET /api/portfolio/holdings/{ticker}/prices; Portfolio button restores whole-portfolio graph. No frozen config changes.
- Checks: 44 focused backend tests passed (holding prices/news/live policy/recorded replay/approve-decline/contracts), 7 frontend tests passed, production build passed. Generated tsbuildinfo restored if tracked; no source edits by Codex.
- New isolated attempt: `backend/runs/smoke/final-ui-20261108T063302Z/`. Recorded SQLite and verified market data copied from prior retest; source protected and copied recording SHA remains unchanged. Backend server PID 40108 / launcher 33308, :8000; frontend Vite PREVIEW PID 39564, :5173. Verify ownership before stopping.
- Frontend serves an isolated PRODUCTION build from attempt/frontend-dist, VITE_MOCK=0, commit 3c4545c. This intentionally does not hot-reload while Mo continues frontend-only source edits. Do not rebuild this directory or pull/restart mid-user-test. Backend/contract/shared-type changes need coordination.
- Demo is read-only recorded replay through 1 Sep 2026, 4 holdings, GBP 10,549.34 NAV. No new Gemini calls. Live remains separate and is real-model capable; no new paid build/check was authorised.
- VS Code integrated browser at /onboarding is under USER CONTROL. It caught the initial health request before backend startup and still showed Market mode unavailable/Internal Server Error at last observation. Subsequent proxy requests to /api/health, /api/portfolio and holding prices returned 200. User was asked to refresh once using the browser's reload arrow. Do not take over their mouse/keyboard. No code fix needed for that observed startup race yet; if it repeats after refresh, investigate.
- Suggested test: Demo -> Open demo timeline -> Home -> click each asset to inspect its adjusted GBP price chart -> Portfolio -> Connections/Matrix/Performance/Split view -> Timeline, Benchmarks, Agents and evidence. User can navigate/replay freely. Avoid Live Build, Run review/check, saving approval preferences or approving/declining new proposals until explicitly testing those actions. Live onboarding may be explored up to plan review before Build.

### Latest: user-driven restart/retest ready (Codex, 8 Nov ~06:23)

- Dev asked to stop the old app, pull main, and restart so he can control the UI. Stopped only our owned continuation/backend processes (38720/32200) and Vite (40940). Fast-forwarded main to 98d48a6. Incoming changes were README, handover and board ONLY; no frontend application changes beyond already-tested #132/#133.
- New isolated directory: `backend/runs/smoke/retest-20261108T062020Z/`. Copied verified market files and SQLite-backed up the completed 41-day continuation into recorded.sqlite. Original source remains intact. `retest.json` stores its SHA256; unchanged after validation/startup.
- Restarted STANDARD app.main:app, not the auto-running continuation helper. RECORDED_RUN points to the new recorded.sqlite, APP_MODE=historical, LLM_MODE=live globally; recorded historical state forces cache-only replay. Demo DB is read-only on disk and copied into memory. Public Live uses a separate fresh mode database and real models if a build is later authorised.
- Current health: historical, 1 Sep 2026, llm_mode=replay, data_source=eodhd; 4 holdings, GBP 10,549.34 NAV. No new paid Gemini run started for retest. Backend server 38660 / launcher 41920; frontend 40592. Verify identities before stopping. Logs are in retest/logs.
- VS Code integrated browser is open at http://127.0.0.1:5173/onboarding . USER CONTROLS IT. Do not click through or open external browser tabs unless requested. Suggested first route: Demo -> Open demo timeline -> Home, inspect Connections/Performance/Split view, Timeline, Benchmarks and saved agent evidence. Playback/navigation is safe. User should NOT click Real Build, approve/decline new proposals or save plan edits until explicitly moving to that test phase. If testing Live onboarding, stop at plan review before Build.
- Do not treat existing asset-selection behavior as fixed: asset clicks currently focus Positions rather than selecting an individual asset performance chart. This remains an acknowledged UI gap.

### Latest: five historical runs completed (Codex, 8 Nov ~06:08)

- Dev authorised continuing Priya through history to five runs total, not four independent new starting portfolios. Completed initial build plus reviews on 21 Jul, 4 Aug, 18 Aug and 1 Sep 2026. All four reviews chose maintain. Simulation is STOPPED at 1 Sep after 41 trading days; do not extend without another instruction.
- Continued in a separate ignored copy: `backend/runs/smoke/20261108T054104Z/continuation-2-to-5/`. `continue_smoke.py` is a local smoke harness, not tracked application code. Original one-day recording/database is preserved. Verified bootstrap reconstructed identical first targets using 13 cached responses and ZERO live calls before starting four new runs. Frozen config and application code were not changed.
- New runs: 21 Jul `run_6d16649396` 28.46s/$0.0321; 4 Aug `run_59d2c5ffc1` 35.54s/$0.0357; 18 Aug `run_d83b184df7` 49.75s/$0.0342; 1 Sep `run_abebca899d` 40.94s/$0.0361. All maintain; estimated additional cost $0.1381. Models: Argon lead, Flash specialists. Reconstructed initial run is `run_b95155e0a9` (original evidence `run_1a9f6c1b7c`).
- Four holdings are now filled: IGLS.LSE, VERG.LSE, VUAG.LSE, VUKG.LSE. Six fills including subsequent contribution purchases. Simulated NAV GBP 10,549.34 from GBP 10,400 contributions; cash GBP 740.55; API TWR approximately 1.493%. 41 history points; all five benchmark series available. These are partial-window simulated results, not the completed four-month evaluation.
- Active local backend is the continuation harness on 127.0.0.1:8000 (server PID 38720, launcher 32200; verify before stopping), serving continuation state.sqlite. Frontend stays :5173. `final_report.json`, portfolio.json, history.json, benchmarks.json and runs.json are saved in the continuation directory. Source market snapshot remains the verified isolated EODHD copy.
- USER PREFERENCE: open app pages inside VS Code's integrated browser from now on, not external browser tabs. Computer-use verification found the integrated browser still on the separate Live quiz. Navigated existing Demo entry -> Open demo timeline -> Home without an extra build. Assets, Connections lattice and Split view performance were visually verified inside VS Code. Keep user on Home. No live Build button was clicked.
- Next: let Dev inspect Home (Connections/Performance/Split view), Timeline and Benchmarks in VS Code and report issues. No deployment or full four-month run. `RECORDED_RUN` remains unset for editable smoke state. The continuation now stores initial sim_mandate, but full final-demo packaging/promotion and retry/resume behavior remain separate work.

### Historical smoke result (Codex, 8 Nov ~05:53)

- User completed Live onboarding to the investment-plan review. Live profile is adventurous; historical Priya remains balanced. UI questions: Review every is trading days (default 10); exclusions currently require exact ticker/sleeve codes, not free text. Mo should add help text.
- Exactly one July 7 construction ran via POST /api/sim/start with start=end=2026-07-07, run_agents=true, approvals=batch_policy. Run `run_1a9f6c1b7c`, proposal `prop_a8faaaa992`: built and approved; all 7 gates passed; 4 holdings each have purpose and evidence IDs. Argon lead + Flash specialists; 13 calls, 55,657 tokens, 80.49 s, estimated $0.1243, budget not exceeded.
- Stop point honoured: sim finished on July 7. Orders are queued for the next close, not filled. No four-month run or deployment. Mode round-trip verified Live adventurous / historical balanced with historical date unchanged.
- Artifacts in `backend/runs/smoke/20261108T054104Z/`: construction_result.json, proposal.json, events_construction.json, data_validation.json, logs. This is a smoke attempt, not a publishable final demo recording; the API capture path does not yet persist the initial sim_mandate metadata required by RecordedReplay.
- Browser link for saved investigation: http://127.0.0.1:5173/runs/run_1a9f6c1b7c . It replays saved events without new Gemini calls. User may inspect it; do not initiate another paid run or advance the simulation without a new instruction.

### Active local smoke test (Codex, 8 Nov ~05:42)

- Latest main was fast-forwarded to 5bd64b2 (incoming changes were README-only); no application code changed.
- Isolated attempt: `backend/runs/smoke/20261108T054104Z/`. Its snapshot contains verified EODHD prices (17,501 rows, 18 instruments) and FX (1,005 rows), through 6 Nov 2026. Existing evidence files were copied with their real/synthetic source labels preserved. Original `backend/data/snapshot/` was not overwritten. Validation and hashes: `data_validation.json`.
- Local backend is running on `http://127.0.0.1:8000`; frontend on `http://127.0.0.1:5173`, VITE_MOCK=0. APP_MODE=historical, LLM_MODE=live, Argon deep / Flash fast; isolated state.sqlite and mode-specific DBs. Logs and launcher PIDs are in the attempt directory. Effective uvicorn server PID was 19544 (verify listener ownership before stopping).
- User is driving onboarding. The thin-left-bar issue was the 62px sidebar layout fixed by Mo in merged PR #133. Codex fast-forwarded local main to e04c7ec (also includes #132 logos), reloaded and visually checked the start screen and first quiz question: 1920px viewport, 1904px main content, 640px centred quiz. Frontend tests: 7 passed. No PR was merged by Codex during this retry. Browser is on the first Real/Paper quiz question; user must stop at investment-plan review before clicking Build. Backend health returns 200; no construction or paid Gemini smoke call has started.
- Next: let the user complete Live onboarding only to the plan review (do not click Build), then switch back to historical Priya and start exactly ONE July 7 construction using existing batch_policy. Do not start the four-month run, deploy, or overwrite any recording. UI changes are owned by Mo; log gaps rather than editing his active files.

### Done (all merged on main)
- **Keys and providers:** #3 EODHD (paid), #27, #54, #55. Alpha Vantage not used; Alpaca deferred (#80).
- **Agents:**
  - #28 loop on real Argon: retries, backup keys, budgets, cache-stable prompts, cost in `run.completed`.
  - #29 tools on the engine and gateway.
  - #30 construction prompts (PR #120): 163 s / 14 calls / $0.18; every holding has a purpose, why-not and evidence.
  - Consistency fix (PR #117).
- **#31 code (PR #121):**
  - Review and trigger plans; escalation rule: adjust only if the mandate is breached, or the news is material and meets `reconsider_if`.
  - **Deterministic news trigger** (`monitors/rules.news_hits`): held tickers, ≥ 2 strong-event headlines in a day.
  - `PORTFOLIO:` line in the context; `get_investment_case {}` returns all cases; trigger kinds get the trigger budget.
- **#74 code (PR #131), agents predict, code sizes:**
  - stock_analyst / news_analyst may add `views`: direction + confidence + evidence, no numbers.
  - Views are validated against tool evidence and sized by `engine.forecast.apply_views` with the **frozen** `max_view_tilt`, under the optimiser's caps. They live 10 trading days. Measured effect ≤ ~1 pp.
  - `runner --no-agent-views` ablation; `--no-forecast` is now honoured by the agents' `build_options` (bug fix).
- **#61 (PR #124):** organisers' finance-kit challenge.
  - markets 24/11/25, real-markets 14/14/32 vs buy-and-hold: "not distinguishable"; 0 provenance flags.
  - Evidence in `eval/finance-kit/`; docs in `docs/finance-kit.md`. Jin asked (#70) to add the "run markets/real-markets" README note.
- **Demo persona:** Priya, balanced (PR #114); historical mode locked by Jin (#119). The recorded run uses the default `--profile balanced`.
- **Deploy:**
  - #56 + #4 dry run: **https://165-22-115-152.sslip.io** (droplet `uclagentverse`, 165.22.115.152, lon1, 2 GB). Currently synthetic + `LLM_MODE=fake`.
  - Cron and `TASK_SECRET` live in the droplet `.env`. Auto-deploy on push is OFF.
- **Config:** `forecast.lambda_return` 0.1 calibrated on real data (PR #103); `max_parallel` 5; **`eval-freeze` tagged by Cem: do not change `backend/app/config/*`.**
- **Closed / descoped:** #20 (Cem built `/api/benchmarks`), #33 (descoped; the code guard remains), #60, #61, #4, #56.

### Next, in order: everything left needs the REAL snapshot first
1. **Dev fetches the real snapshot** (Dev's own step; can be redone safely, since it's git-ignored):
   - `cd backend; $env:PYTHONIOENCODING='utf-8'; .venv/Scripts/python scripts/fetch_snapshot.py`
   - Check that `data/snapshot/manifest.json` says `"label": "eodhd"`.
   - To get back to synthetic: `scripts/make_synthetic_snapshot.py`.
2. **Engine-only check:** `.venv/Scripts/python -m app.sim.runner --start 2026-07-07 --end 2026-11-06 --no-agents --record runs/no_agents.sqlite`. It takes ~1 min; read the `Triggers:` line, especially `news N`. If `news` is huge, tighten `NEWS_STRONG` / `NEWS_MIN_STRONG` in `monitors/rules.py` (code, not frozen config) and tell Cem.
3. **#31 live hero checks (≤ 6 Argon runs), then close #31.** A small scratch script:
   - Load the real snapshot, set the clock to the hero date, seed the ledger with the persona portfolio **plus a small position in the hero stock**.
   - Run `supervisor.start("news", "<headline> (<news id>)")`. The events come from the board post `…hero-event-candidates…`.
   - Runs:
     - 1 review run (mid-window): expect **maintain** with a reason.
     - **AAPL 31 Jul** (guidance / supply) and **NVDA 27 Aug** (growth): expect a **material** triage; adjust only if it meets the case.
     - **NVDA 31 Jul** (Burry/Cuban warning) and **AAPL 27 Oct** (Cuban comment): expect **maintain with an explanation**.
     - 1 retry.
   - Post the results on the board; report honestly (they're agent judgements, not forced outcomes).
4. **#74 live check, then close #74:**
   - ≤ 2 live runs: a view gets validated and applied (`calc.result agent_view_tilt`).
   - **2-week slice ablation:**
     - `runner --start 2026-07-07 --end 2026-07-20 --agents --approvals batch_policy --record runs/slice_views.sqlite`
     - the same with `--no-agent-views --record runs/slice_noviews.sqlite`
     - Compare NAV, turnover and decisions; post as a small-sample check.
5. **#38 retrospective lessons** (Dev decided: after the snapshot): 0–3 advice lessons after every agent run; spec in docs/05 §9 and the #38 issue. **Only appears in the recording if built before step 6.**
6. **#37 the 4-month agent run (Dev runs it, laptop awake ~1 h):** the 2-week slice timing first, then `--agents --approvals batch_policy --record runs/year.sqlite`. Then post the sha256 of `runs/*.sqlite` on the board.
7. **#13 final deploy, only after it all works locally (Dev's rule):**
   - Copy `backend/data/snapshot/*` + `runs/*.sqlite` to `/opt/uclagentverse/var/` (`scp` / `tar | ssh root@165.22.115.152`).
   - Set `LLM_MODE=replay` in the droplet `.env`.
   - `ssh root@165.22.115.152 'cd /opt/uclagentverse && git pull && docker compose up -d --build'`.
   - Smoke test `https://165-22-115-152.sslip.io/api/health`. Check that `data_source` is no longer synthetic.
8. **Later:** #39 pitch content, #69 rehearsal; before the 07:00 freeze, the secret scan `python .agents/skills/review-and-push/scripts/preflight.py` (needs Gitleaks); after judging, #57 cancel EODHD and revoke keys, #14 destroy the droplet.

**Known:** construction takes ~163 s on Argon; the demo replays the recording; live builds stream. Each Argon call takes ~15–25 s.

### Environment (Dev's PC: Windows, Git Bash + PowerShell)
- `.env` in the repo root has every key (git-ignored; **never print, log or commit keys**). `LLM_MODE=live`; `GEMINI_MODEL_DEEP=gemini-4-argon` and `GEMINI_MODEL_FAST=gemini-3.8-flash` (Dev authorised mixed-model routing, #127). Existing deep roles stay on Argon; fast roles use Flash. Existing all-Argon cache replays need their original `GEMINI_MODEL_FAST=gemini-4-argon` setting; do not replace canonical recordings or compare runs without disclosing their models. Credits are free but finite: don't waste them, and use `LLM_MODE=fake` for anything that isn't a deliberate live check.
- Venv: `backend/.venv` → run `cd backend && .venv/Scripts/python -m pytest -q` (`make` assumes Unix paths).
- Prefix `PYTHONIOENCODING=utf-8` for `scripts/board.py` and `check_providers.py`. Always pass `encoding="utf-8"` when reading or writing text files (Windows defaults to cp1252).
- The synthetic snapshot is in `backend/data/snapshot` (git-ignored). Manual live run: `cd backend && STATE_DB=<scratch path>.sqlite .venv/Scripts/python -m app.agents.supervisor --run construction` (about $0.04; reruns are free from the cache).
- `EDGAR_USER_AGENT` now contains the contact Dev supplied, in ignored `.env`. No further contact information or SEC credentials are needed; do not print it.
- News sources: **Finnhub (US) + EODHD (UK). Alpha Vantage is NOT used.** Alpaca is deferred (#80).
- Organiser skills kept in `.agents/skills/` (`finance-test`, `review-and-push`). **Never copy kit `.py` files elsewhere in the repo**, and keep these strings out of our code: `from bench/testbed/core`, `answers.jsonl`, `SEED-REVEAL`, `AGENTVERSE_CHALLENGE`, `data.binance.vision`. The challenge's provenance scan flags them (docs/finance-kit.md).
- **Before the 07:00 freeze:** run the secret scan `python .agents/skills/review-and-push/scripts/preflight.py` (needs Gitleaks v8.30.1+). If a key was ever committed, rotate it.
- Judging (organisers' builder guide): live software, a named user, a verification loop, a human approval gate, a demo **under 3 min**, and a README with exact model IDs + the verification loop. The deck/README (#39/#70) must say this.

### How to work here
- **Teammates push to `main` constantly:** `git fetch && git merge origin/main` into your branch at the start, before every commit, and right before opening and merging a PR. Commit before merging; never `git checkout origin/main -- .` over your work.
- Rules: data only via `DataGateway` with `as_of`; numbers only from `backend/app/engine/`; emit an event for every step; contract or config changes need a board post; branch `dev/<issue>-<slug>`; PR with `Closes #n`; self-merge only when CI is green. Ask before editing other people's folders (see AGENTS.md §2).
- Test patterns: `tests/test_tools.py` (call tools via `state.supervisor.tools.call`) and `tests/test_supervisor.py` (stub Gemini client). Tests must never hit the network.

### Hand-off prompt (paste this into the next agent)

```
You're taking over Dev's work on the UclAgentVerse hackathon repo (an AI investment team for first-time UK investors). Dev's previous agent ran out of credits.

1. Read AGENTS.md, then docs/HANDOVER-dev.md ("Resume here" at the top).
2. Run `git pull`, then `$env:PYTHONIOENCODING='utf-8'; python scripts/board.py list --to dev --open`, and act on anything addressed to dev or all.
3. Do the next item in "Next, in order" in the handover. Read its GitHub issue first with `gh issue view <n>`.

Rules:
- Teammates push to main constantly. Run `git fetch && git merge origin/main` into your branch at the start, before every commit, and before opening and merging a PR. Commit before merging, and never overwrite your work.
- Never print, log or commit API keys or .env contents.
- Use LLM_MODE=fake unless you're doing a deliberate live check. The Gemini credits are limited.
- This is Windows: use backend/.venv/Scripts/python, PYTHONIOENCODING=utf-8 for the board script, and encoding="utf-8" when reading or writing files.
- Tests must not use the network. Run `cd backend && .venv/Scripts/python -m pytest -q` (and the frontend build if you touched it) before every PR.
- Only edit Dev's areas (AGENTS.md section 2). Post on the board before changing shared files.
- Never copy files from ../agentverse into the repo except into .agents/skills/, and keep kit names (bench, testbed, answers.jsonl, AGENTVERSE_CHALLENGE, data.binance.vision) out of our code. The organisers' provenance scan flags them. See docs/finance-kit.md.
- Open a PR with "Closes #<n>" and merge only after CI passes.

Before you stop for any reason, update the "Resume here" section in docs/HANDOVER-dev.md and push it.
```

### Before handing back
Update this section (done / half-done / branch), push, and post a board `handoff` to `dev` if anything is mid-flight.

## Start of every session
```bash
git pull && python scripts/board.py list --to dev --open
gh issue list --label owner:dev --label mvp     # mvp before feature, always
```

## Your timeline

| By | Do | Issues |
|---|---|---|
| **23:15** | Clone, `cp .env.example .env`, add `GEMINI_API_KEY` + `GEMINI_MODEL_FAST` + `LLM_MODE=live`, `make setup && make synth && make test`, `python -m app.agents.llm --ping` | #27 |
| **23:45** | Sign up for Finnhub, EODHD free, Alpaca (optional); set `EDGAR_USER_AGENT`; run `python scripts/check_providers.py --eodhd-max 15 --report ../provider-report.md`; if London tickers are listed, **pay EODHD $19.99**, rerun `--only eodhd` | #3 #54 #55 |
| **00:00** | **Send the keys privately to Jin** (he downloads the real snapshot) · post the provider report on the board | #55 |
| **00:30** | Get the AgentVerse finance kit + understand its hidden test mode → `docs/finance-kit.md` | #60 |
| **01:00** | Agent loop on real Gemini (schema retries, budgets, tokens) | #28 |
| **01:30** | Core tools against engine + gateway (incl. the `forecast` tool from Cem's #73) | #29 |
| **02:00** | Construction plan + prompts → real proposal; `make fixtures` and push (**switch 2**) | #30 |
| **02:30** | Review/trigger plans · benchmarks wired into Cem's loop · **M1 integration + `eval-freeze` tag** · 2-week slice, timed | #31 #20 #37 |
| **03:00** | **Launch the 4-month agent run** (~1 h), then the `--no-agents` baseline | #37 |
| **04:15** | Post `runs/year.sqlite` + `runs/no_agents.sqlite` (**switch 4**) | #37 |
| **03:00–04:15** | **Deploy dry run** (droplet, HTTPS, current main) while the agent run goes | #4 |
| 03:00–06:30 | Assurance gate → injection guard → finance-kit run → explainer (gate/guard/explainer are `feature`, but do them if MVP is done: they're the differentiator) | #32 #33 #61 #34 |
| **06:30** | **Second deploy** with the recorded runs + smoke test. DigitalOcean account + billing ready **before 03:00** | #13 #56 |
| 07:00 | **Feature freeze**: bug fixes only | |
| 07:00–09:00 | Fixes · **08:00 final deploy** · voice-over 08:00–08:30 · smoke test the link 08:30 (demo with no keys + live) | #13 |
| 01:30 → 09:30 | **Slide text to Jin in batches** (story by 03:00, controls by 05:00, eval by 08:30); Mo builds the video in parallel | #39 |
| 09:00–12:20 | Q&A cheat sheet · review deck (10:30) + video (10:30) · deck PDF 11:00 · rehearsal · submit 12:20 | #39 #69 |
| After judging | **Teardown**: destroy droplet, cancel EODHD, revoke keys | #14 #57 |
| After judging | Cancel EODHD, revoke keys | #57 |

Features only if ahead: #35 chat, #36 monitor designer, #38 retrospective, #63 Companies House, #64 macro, #65 FCA-grounded compliance, #74 agent views.

## Decisions already made
- You own: **all deploys** (#4, #13, #14), Gemini agents, all paid/external APIs (accounts, payment, keys, adapters, `check_providers.py`), finance kit (#60/#61), benchmarks (#20), deck + pitch (#39/#69).
- **Sim window: 7 Jul → 6 Nov 2026** (4 months, fully after Argon's reported Mar 2026 cutoff). Engine-only baseline over the same window = "what Gemini adds".
- Walk-forward: nothing sees data after the sim day (`test_no_peeking`, #72). 2-week forecast is code-made from past data (#73).
- Finance kit = organisers' synthetic test data, reported separately from our real-data replay.
- Data sharing: 4 announced switch moments (docs/13). `runs/year.sqlite` is the single source of truth.
- Payments: EODHD $19.99 (one month); DigitalOcean 2GB droplet only from the 03:00 dry run until after judging.
- Labels: every `mvp` issue before any `feature`.

## Open items
- Who runs the 03:00 agent run (laptop awake + online until ~04:15)? Decide at the 02:30 integration.
- "2 weeks" means a 2-week horizon/cadence using all history up to the sim day (assumed; say if you meant otherwise).
