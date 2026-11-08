# Dev: what to do now (Codex handoff, Sun 8 Nov 2026)

Any agent can pick this up (Claude Code, Codex/GPT, Gemini CLI, Cursor), for example while Dev's Claude credits reset. Read `AGENTS.md` first; the team timeline is in `docs/09-build-plan.md`. **Goal: one public link with demo + live mode, everything working by 09:00. The demo never waits on an API call. Submit by 12:20.**

## Resume here: current state (keep this section updated)

**Resume at #30.** #7 is complete and merged in [PR #93](https://github.com/Prittstick22/UclAgentVerse/pull/93), merge `db8c36a`; issue #7 is closed and both backend/frontend CI jobs passed. Dev confirmed the SEC EDGAR integration is okay after discussing its purpose. A rollback was briefly requested but stopped before any revert command ran; nothing was reverted.

**Current implementation state:** no #30 code or prompt changes have been made, no live #30 construction check has run, no #30 fixtures have been regenerated, and no #30 PR is open. `dev/30-construction-prompts` exists remotely with documentation-only checkpoint work. This handover is being published to `main` at Dev's explicit request so the next agent can resume. Pull `main`, read the board, then reuse that branch and merge `origin/main` before starting #30. No work is half-implemented.

**Local data:** #7 fetched real news, 29 SEC filings and 3 earnings rows into ignored `backend/data/snapshot/`; see `docs/fetch-text.md` for ticker counts and coverage limits. Those files are not pushed to GitHub. Price/FX files were untouched by #7; do not assume this local directory is a complete real-data snapshot or relabel its manifest. Coordinate the combined real snapshot with Jin. The EDGAR contact is configured in ignored `.env`; no SEC account, API key or payment is needed. Never print or commit the contact setting or other credentials.

### Done
- **#7 complete (PR #93 merged):** dated news/filings/earnings fetch, three-line snapshot hook preserving Jin's #6, 58 offline backend tests passing and frontend build/CI passing. Live-fetched news, 29 filings and 3 earnings rows; sparse evidence and provider limits documented in `docs/fetch-text.md`. AAPL/NVDA hero candidates posted to the board for Cem/Jin. Local text files remain ignored and need separate snapshot sharing.
- #3 EODHD bought + verified (every ticker from 2023-01, LSE units OK, delayed quotes OK) · #27 Gemini ping · #54 keys · #55 provider check (PR #81)
- **#28 agent loop on real Argon (PR #88):** schema retry, Gemini retries + backup keys (`GEMINI_API_KEY_BACKUPS`), per-step token budget, cache-stable prompts, `cost_estimate_usd`/`duration_s` in `run.completed`, `RunSummary` in kv `runs`. About 1,850 tokens and $0.007 per call, about 10 s per call; reruns cost 0 tokens.
- **#29 core tools (PR #90):** tools wired to engine + gateway; construction runs end `built` with a `Proposal` (live Argon: 6 calls, $0.044). `gw.earnings()` added (past dates only). The `forecast` tool returns `not_available` until Cem's #73 lands (`app.engine.forecast.forecast(gw, tickers, as_of, horizon=10)`).
- #7 reassigned from Jin to Dev (board handoff posted to Jin).
- **#60 finance kit reviewed:** see `docs/finance-kit.md`. The organisers' kit is at `../agentverse/` (outside the repo, never commit it). Their hidden **challenge** mode is how unseen-data testing is likely judged; the packs that fit us are `markets` and `real-markets`.

### Next, in order (mvp before feature)
**State at ~03:50 Sun:** main is clean; no open Dev branches or PRs. Done since the last hand-off: #30 construction prompts (PR #120: 163 s / 14 calls / $0.18 on Argon, every holding has purpose + why-not + evidence; fixtures regenerated from that real run with `make_fixtures.py --from-db`), the consistency fix (PR #117: `build_options` uses the engine forecast tilt, `risk_stats` tool = `engine.risk.risk_stats`), the demo persona Priya/balanced (PR #114; Jin locked historical mode in #119), #56 + #4 dry run (**https://165-22-115-152.sslip.io**, droplet 165.22.115.152, synthetic + fake), #20 closed (Cem built it in #109), `forecast.lambda_return` 0.1 calibrated on real data (PR #103), `max_parallel` 5.
1. **#37 the 4-month run, run by Dev himself, locally first:** fetch the real snapshot (`scripts/fetch_snapshot.py`), wait for Cem's `eval-freeze` tag, then the timed 2-week slice → full `--agents --approvals batch_policy --record runs/year.sqlite` → `--no-agents --record runs/no_agents.sqlite` (default `--profile balanced`). **Deploy to the droplet only after it works locally (Dev's rule).**
2. **#31: code done (PR #121 merged; #31 still open).** Remaining: live hero-event checks on the real snapshot (≤ 6 Argon runs): 1 review run + AAPL 31 Jul, NVDA 27 Aug (material candidates), NVDA 31 Jul, AAPL 27 Oct (alarming-but-immaterial candidates), each with a small seeded position in the hero stock; post results; close #31. Engine-only run first to see `Triggers: news N`.
3. **#61 done** (PR #124): challenge results in docs/finance-kit.md + `eval/finance-kit/`; Jin to add the 'run markets/real-markets' note to the README (#70).
4. **#13 final deploy** once the runs exist: copy `backend/data/snapshot/*` + `runs/*.sqlite` to `/opt/uclagentverse/var/`, set `LLM_MODE=replay` in the droplet .env, `docker compose up -d --build`, smoke test. Auto-deploy on push stays OFF.
5. Features only if ahead: #32 minimal assurance gate (critic + code checks) is the most valuable; #38 lessons (0–3 per run, advice only).
Known: construction takes ~163 s on Argon (floor = the lead's 4 sequential steps + the slowest specialist); the demo replays the recording, and live builds stream.

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
