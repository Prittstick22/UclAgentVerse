# Dev: what to do now (Codex handoff, Sun 8 Nov 2026)

Any agent can pick this up (Claude Code, Codex/GPT, Gemini CLI, Cursor), for example while Dev's Claude credits reset. Read `AGENTS.md` first; the team timeline is in `docs/09-build-plan.md`. **Goal: one public link with demo + live mode, everything working by 09:00. The demo never waits on an API call. Submit by 12:20.**

## Resume here: current state (keep this section updated)

**Handed over Sun 8 Nov ~05:15** (Dev's Claude credits ran low; Dev will be back). `main` is clean; **no Dev branches or PRs open**, and nothing is half-done. The one open PR is Mo's #132 (holding logos), not Dev's.

**Model note:** the session switched Opus 5.5 → Sonnet 5.5 at ~05:00 and **back to Opus 5.5** at ~05:10. Use whatever attribution line your own harness gives you. When you post live-run results, say which model produced them.

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
