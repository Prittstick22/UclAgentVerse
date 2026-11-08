# Dev: what to do now (updated Sun 8 Nov 01:20)

Any agent can pick this up (Claude Code, Codex/GPT, Gemini CLI, Cursor), for example while Dev's Claude credits reset. Read `AGENTS.md` first; the team timeline is in `docs/09-build-plan.md`. **Goal: one public link with demo + live mode, everything working by 09:00. The demo never waits on an API call. Submit by 12:20.**

## Resume here: current state (keep this section updated)

**Checkpoint Sun 8 Nov:** #7 is merged in PR #93 (`db8c36a`), both CI jobs passed and the issue is closed. The requested rollback was stopped before any revert command ran; Dev subsequently confirmed the EDGAR integration is okay. Active branch: `dev/30-construction-prompts`; no #30 implementation changes yet. Next: #30 prompts and a timed deliberate live construction check. See `docs/fetch-text.md` for measured coverage and limitations. EDGAR contact is configured in ignored `.env`; no additional credentials are needed.

### Done
- **#7 complete (PR #93 merged):** dated news/filings/earnings fetch, three-line snapshot hook preserving Jin's #6, 58 offline backend tests passing and frontend build/CI passing. Live-fetched news, 29 filings and 3 earnings rows; sparse evidence and provider limits documented in `docs/fetch-text.md`. AAPL/NVDA hero candidates posted to the board for Cem/Jin. Local text files remain ignored and need separate snapshot sharing.
- #3 EODHD bought + verified (every ticker from 2023-01, LSE units OK, delayed quotes OK) · #27 Gemini ping · #54 keys · #55 provider check (PR #81)
- **#28 agent loop on real Argon (PR #88):** schema retry, Gemini retries + backup keys (`GEMINI_API_KEY_BACKUPS`), per-step token budget, cache-stable prompts, `cost_estimate_usd`/`duration_s` in `run.completed`, `RunSummary` in kv `runs`. About 1,850 tokens and $0.007 per call, about 10 s per call; reruns cost 0 tokens.
- **#29 core tools (PR #90):** tools wired to engine + gateway; construction runs end `built` with a `Proposal` (live Argon: 6 calls, $0.044). `gw.earnings()` added (past dates only). The `forecast` tool returns `not_available` until Cem's #73 lands (`app.engine.forecast.forecast(gw, tickers, as_of, horizon=10)`).
- #7 reassigned from Jin to Dev (board handoff posted to Jin).
- **#60 finance kit reviewed:** see `docs/finance-kit.md`. The organisers' kit is at `../agentverse/` (outside the repo, never commit it). Their hidden **challenge** mode is how unseen-data testing is likely judged; the packs that fit us are `markets` and `real-markets`.

### Next, in order (mvp before feature)
1. **#7 complete: PR #93 merged.** The implementation plan below is retained as reference; do not redo it. Next active issue is #30.
   - New `backend/scripts/fetch_text.py` with steps `news`, `filings`, `earnings`. Only a **3-line hook** in `backend/scripts/fetch_snapshot.py` (Jin is editing that file for #6 prices; don't touch the rest).
   - Add `EODHD.news(symbol, start, end, limit, offset)` to `backend/app/data/adapters/eodhd.py` (`GET https://eodhd.com/api/news?s=<TICKER>&from=&to=&limit=&offset=&api_token=&fmt=json`; returns `[{date, title, content, link, symbols, sentiment?}]`). Reuse `Finnhub.company_news` / `Finnhub.earnings_calendar` (`adapters/finnhub.py`) and `Edgar.submissions` / `Edgar.document` (`adapters/edgar.py`).
   - **News:** Finnhub `company_news` for each US stock (catalogue `kind == "stock"`, `.US`), month by month from 2026-06-01 to today, using the plain symbol (`AAPL`); EODHD news for each `.LSE` stock over the same window. Map to the `NewsItem` schema (`backend/app/data/models.py`), `source` = `finnhub` / `eodhd`, dedupe by URL. **`available_at`**: if published on a weekday at or before 16:30 Europe/London, that time; otherwise the next weekday at 16:30 London (the `SimClock` observes each day at 16:30, `backend/app/core/clock.py`). Append the labelled synthetic injection item from `backend/scripts/make_synthetic_snapshot.py` (`news_syn_inject`, `synthetic: true`).
   - **Filings:** EDGAR submissions for the US stocks (CIKs: AAPL 320193, MSFT 789019, NVDA 1045810, AMZN 1018724). 10-K/10-Q/8-K with `acceptanceDateTime` ≥ 2026-06-01; fetch the primary document (`https://www.sec.gov/Archives/edgar/data/<cik>/<accession no dashes>/<primaryDocument>`), strip HTML, keep 3–10 paragraphs ≤ 600 chars mentioning risk/supplier/guidance/revenue. Map to `Filing` (passage ids `<filing id>#p<n>`); `available_at` uses the same rule as news. SEC wants a contact in `EDGAR_USER_AGENT` and ≤ 10 requests/s.
   - **Earnings:** Finnhub `earnings_calendar(start="2023-01-01", end=today, symbol=…)` per US stock → `earnings.jsonl` rows `{ticker: "AAPL.US", date, source: "finnhub"}`. UK earnings aren't on the free plans: write that in the console summary.
   - Write `news.jsonl`, `filings.jsonl` and `earnings.jsonl` (one JSON object per line) to `--out` (default `backend/data/snapshot`). Never overwrite Jin's price files.
   - **Tests** (`backend/tests/test_fetch_text.py`, offline, stub adapters): the `available_at` rule (before/after 16:30, Friday evening → Monday, weekend), mapping + dedupe, passage extraction, and `gw.news()` never returns items after as_of on fetched-shape rows.
   - Then run it for real (keys in `.env`), report counts per ticker, and post a board `fyi` with a shortlist of **hero events** from real 7 Jul – 6 Nov 2026 headlines: one *material* (→ adjust) and one *alarming but immaterial* (→ maintain) per hero pick (docs/06 §6), for Cem/Jin to agree. PR `Closes #7`, board post to Jin.
2. **#30 prompts** (also: remove `temperature=0.2` from `LLM._call_live` in `agents/llm.py`, because Argon ignores it with a deprecation warning; optionally pass `thinking_level`, see docs/finance-kit.md) (`backend/app/agents/prompts/*.md`, `roles.py`). The live lead asks for a non-existent `scout` role: list the exact role names it may spawn (`RESEARCH_SPAWNABLE` in `roles.py`) and the tool arguments (`weights` or `option`). Then run `--run construction` live and check that the spawns are accepted.
3. #31 review/trigger plans → #20 benchmarks → #37 the 2-week slice, then the 4-month run at 03:00 (**config frozen at the 02:30 `eval-freeze` tag**).
3b. **#61 finance-kit adapter** (do it while the 4-month run is going): `backend/app/eval/finance_kit_adapter.py`. Read stdin JSONL, reply on stdout and log to stderr only. For `market_step`, use a deterministic rule built on `app.engine.risk` from the observed history only (stay invested; go to cash on a fixed drawdown/vol band breach; re-enter when calm), with constants fixed before any challenge run. Return `{"error":"unsupported_task"}` for cashflow/transactions. **Never import kit code** (challenge mode scans for it). Add an offline test. Practise with `python ../agentverse/finance/bench.py generate/run`, then run `bench.py challenge --pack markets` and `--pack real-markets` and commit the REPORT/COMMITMENT/SEED-REVEAL under `eval/finance-kit/`. Report results honestly vs buy-and-hold, labelled "organiser synthetic test data". Full spec: `docs/finance-kit.md`.
4. Before 03:00: DigitalOcean account + billing for Jin (#56): Dev does this himself.

### Environment (Dev's PC: Windows, Git Bash + PowerShell)
- `.env` in the repo root has every key (git-ignored; **never print, log or commit keys**). `LLM_MODE=live`; `GEMINI_MODEL_DEEP` and `GEMINI_MODEL_FAST` are **both `gemini-4-argon`** (team decision). Fallback if rate limits bite: `GEMINI_MODEL_FAST=gemini-3.8-flash`. Credits are free but finite: don't waste them, and use `LLM_MODE=fake` for anything that isn't a deliberate live check.
- Venv: `backend/.venv` → run `cd backend && .venv/Scripts/python -m pytest -q` (`make` assumes Unix paths).
- Prefix `PYTHONIOENCODING=utf-8` for `scripts/board.py` and `check_providers.py`. Always pass `encoding="utf-8"` when reading or writing text files (Windows defaults to cp1252).
- The synthetic snapshot is in `backend/data/snapshot` (git-ignored). Manual live run: `cd backend && STATE_DB=<scratch path>.sqlite .venv/Scripts/python -m app.agents.supervisor --run construction` (about $0.04; reruns are free from the cache).
- `EDGAR_USER_AGENT` still has a placeholder email: ask Dev for the team email.
- News sources: **Finnhub (US) + EODHD (UK). Alpha Vantage is NOT used.** Alpaca is deferred (#80).
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
