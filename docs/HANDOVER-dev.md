# Dev: what to do now (updated Sat 7 Nov 22:55)

You're on your PC with Claude Code. Read `CLAUDE.md`/`AGENTS.md` first; the team timeline is in `docs/09-build-plan.md`. **Goal: one public link with demo + live mode, everything working by 09:00. The demo never waits on an API call. Submit by 12:20.**

## Start of every session
```bash
git pull && python scripts/board.py list --to dev --open
gh issue list --label owner:dev --label mvp     # mvp before feature, always
```

## Your timeline

| By | Do | Issues |
|---|---|---|
| **23:15** | Clone, `cp .env.example .env`, add `GEMINI_API_KEY` + `GEMINI_MODEL_FAST` + `LLM_MODE=live`, `make setup && make synth && make test`, `python -m app.agents.llm --ping` | #27 |
| **23:45** | Sign up for Finnhub, Alpha Vantage (2–3 keys), EODHD free, Alpaca (optional); set `EDGAR_USER_AGENT`; run `python scripts/check_providers.py --eodhd-max 15 --report ../provider-report.md`; if London tickers are listed, **pay EODHD $19.99**, rerun `--only eodhd` | #3 #54 #55 |
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
