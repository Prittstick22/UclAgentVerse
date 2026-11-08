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
1. **#7 done; do not redo it.** PR #93 merged. AAPL/NVDA material and alarming-but-potentially-immaterial hero-event candidates were posted for Cem/Jin in `board/messages/20261108T002122Z-dev-to-all-text-fetch-ready-and-hero-event-candidates-for-c.md`. These are investigation hypotheses, not pre-approved trades; no later returns were used to establish them.
2. **Small follow-up (do with #30):** Cem's PR #92 added `engine.risk.risk_stats(weights, prices, benchmark=None, lookback=None)`. Switch the `risk_stats` tool in `agents/tools.py` to call it instead of assembling vol/drawdown/beta itself (rule 2: numbers come from the engine). Cem's #94 optimiser accepts `req.mu` (forecast); `build_options` can pass it once #73's forecast exists.
2. **#30 prompts** (also: remove `temperature=0.2` from `LLM._call_live` in `agents/llm.py`, because Argon ignores it with a deprecation warning; optionally pass `thinking_level`, see docs/finance-kit.md) (`backend/app/agents/prompts/*.md`, `roles.py`). The live lead asks for a non-existent `scout` role: list the exact role names it may spawn (`RESEARCH_SPAWNABLE` in `roles.py`) and the tool arguments (`weights` or `option`). Then run `--run construction` live and check that the spawns are accepted.
   - Read `gh issue view 30`, `docs/05-agent-system.md` section 7, and `docs/03-how-it-works.md` section 1. Work in Dev's agent area; keep engine numbers deterministic.
   - Replace the placeholder prompts for lead, equity_scout, bond_scout, stock_analyst, risk_analyst and filing_reader. Lead delegates to scouts and risk, plus stock analyst only when the mandate allows stocks; builds three options, saves investment cases with purpose/evidence/reconsider_if, then proposes the selected option for approval.
   - Inspection findings to account for: supervisor currently gives each agent six steps/eight tool calls, compacts tool results to 1,500 characters and ten list items, and does not include the mandate in its prompt header. Check whether this hides candidate holdings/evidence or prevents completing the construction flow before changing anything. Do not change frozen config to work around prompt problems.
   - Acceptance: a deliberate live Argon run builds a sensible portfolio in under two minutes, valid spawns are accepted, every holding has a purpose and evidence IDs, and real-run fixtures are generated for Mo with accurate data provenance. Post on the board before changing shared fixtures; do not label synthetic prices as real market data.
   - Use `LLM_MODE=fake` for development/offline tests. Use a scratch state DB for the deliberate live check. Run the full backend suite and frontend build, record measured duration/cost and limitations, open a PR with `Closes #30`, and merge only after CI is green.
3. #31 review/trigger plans → #20 benchmarks → #37 the 2-week slice, then the 4-month run at 03:00 (**config frozen at the 02:30 `eval-freeze` tag**).
3b. **#61 finance-kit adapter** (do it while the 4-month run is going): `backend/app/eval/finance_kit_adapter.py`. Read stdin JSONL, reply on stdout and log to stderr only. For `market_step`, use a deterministic rule built on `app.engine.risk` from the observed history only (stay invested; go to cash on a fixed drawdown/vol band breach; re-enter when calm), with constants fixed before any challenge run. Return `{"error":"unsupported_task"}` for cashflow/transactions. **Never import kit code** (challenge mode scans for it). Add an offline test. Practise with `python ../agentverse/finance/bench.py generate/run`, then run `bench.py challenge --pack markets` and `--pack real-markets` and commit the REPORT/COMMITMENT/SEED-REVEAL under `eval/finance-kit/`. Report results honestly vs buy-and-hold, labelled "organiser synthetic test data". Full spec: `docs/finance-kit.md`.
4. Before 03:00: DigitalOcean account + billing for Jin (#56): Dev does this himself.

### Environment (Dev's PC: Windows, Git Bash + PowerShell)
- `.env` in the repo root has every key (git-ignored; **never print, log or commit keys**). `LLM_MODE=live`; `GEMINI_MODEL_DEEP` and `GEMINI_MODEL_FAST` are **both `gemini-4-argon`** (team decision). Fallback if rate limits bite: `GEMINI_MODEL_FAST=gemini-3.8-flash`. Credits are free but finite: don't waste them, and use `LLM_MODE=fake` for anything that isn't a deliberate live check.
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
