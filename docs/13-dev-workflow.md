# 13 · Dev workflow

## Setup

```bash
git clone https://github.com/Prittstick22/UclAgentVerse && cd UclAgentVerse
cp .env.example .env            # fill in what you have; everything works with none
make setup                      # backend venv + pip install -e .[dev], frontend npm install
make synth                      # SYNTHETIC snapshot → backend/data/snapshot/
make test                       # pytest
make dev-api                    # :8000
make dev-web                    # :5173, proxies /api → :8000; VITE_MOCK=1 uses fixtures/
```

## Environment variables (`.env.example`)

| Var | Default | Meaning |
|---|---|---|
| `APP_MODE` | `historical` | `historical` or `live` at startup |
| `LLM_MODE` | `fake` | `fake` (offline canned), `live` (Gemini), `replay` (cache only) |
| `GEMINI_API_KEY` | — | DeepMind-provided key |
| `GEMINI_MODEL_DEEP` / `GEMINI_MODEL_FAST` | `gemini-4-argon` / set a Flash ID | Models |
| `EODHD_API_KEY`, `FINNHUB_API_KEY`, `ALPACA_KEY_ID`, `ALPACA_SECRET_KEY` | — | Data providers |
| `EDGAR_USER_AGENT` | `UclAgentVerse team <team-email>` | SEC asks for a contact |
| `SNAPSHOT_DIR` | `backend/data/snapshot` | Snapshot location |
| `STATE_DB` | `backend/state.sqlite` | Events, ledger, memory, LLM cache |
| `PUBLIC_DEMO`, `DEMO_PASSCODE`, `TASK_SECRET`, `DAILY_LLM_BUDGET_USD`, `RATE_LIMIT_PER_MINUTE` | `0`, —, —, `20`, `30` | Deploy safety (#12) |

## Branches and PRs

- `main` is always deployable. Branch `<name>/<issue>-<slug>`.
- **PR title:** `feat(area): summary (#issue)`. The body has `Closes #n` + the acceptance checklist.
- **CI** (`.github/workflows/ci.yml`): backend `pytest`, frontend `npm run build`. Merge when green.
- **Board-only commits** (`board/messages/*`) may go straight to `main`.

## Testing rules

- No network in tests. Use the synthetic snapshot fixture and `LLM_MODE=fake`.
- **Every engine function has a test.** Every control has a test that proves it blocks:
  - `test_mandate_blocks_concentration`
  - `test_gateway_refuses_future`
  - `test_supervisor_refuses_depth3`
  - `test_guard_quarantines_injection`

## Fixtures for the frontend

- `make fixtures` runs `backend/scripts/make_fixtures.py`.
- It writes `fixtures/*.json`: a sample event stream from a fake construction run, plus sample responses for every GET endpoint.
- The frontend's mock mode serves these. Regenerate them whenever contracts change.

## Data sharing: who has which data, and when to switch

Everyone's local `backend/state.sqlite` is **throwaway**: events, ledger and LLM cache from your own testing. It differs per person and that's fine. Delete it any time; it's recreated on start.

What must be identical for everyone is shared as **files**, and there are four switch moments. Each one is announced with a board `handoff` to `all` plus a WhatsApp ping. **Don't switch before the post; switch as soon as you see it.**

| # | Switch | Who posts | Target time | What everyone does |
|---|---|---|---|---|
| 1 | **Synthetic → real snapshot** | Jin (#6, #7) | ~00:00 | Download the zip from the link in the post. Replace `backend/data/snapshot/` with it, delete `backend/state.sqlite`, restart the API. Check with `make data-status`: label `eodhd`, and the sha256 must match the post. **From now on, never run `make synth`.** |
| 2 | **Fixtures from real agent output** | Dev (#30) | ~01:30 | `git pull`. `fixtures/` now holds a real construction run. Mo's mock mode updates automatically |
| 3 | **Config freeze** (`eval-freeze` tag) | Dev + Cem (#37) | 02:30 | `git pull`. From here, `backend/app/config/*` may not change (AGENTS.md rule 5) |
| 4 | **Recorded run ready** (`runs/year.sqlite`, the 4-month window) | Cem / whoever runs the batch (#37) | ~07:00 | Download it and put it in `backend/runs/year.sqlite`. Start the API with `STATE_DB=backend/runs/year.sqlite`. This is the **single source of truth** for replay, the eval numbers and the deployed demo. **Nobody reruns the year after this.** Work on a copy if you need to experiment |

Rules:
- **One copy of the snapshot.** Jin downloads it once; nobody re-downloads their own (different download times give different data).
- **One machine runs the overnight batch,** awake, plugged in and online from 03:00 to 07:00 (sleep disabled). Its `year.sqlite` also contains the Gemini response cache, so any later rerun from that file is free.
- **Large files never go in git** (`backend/data/snapshot/*` and `backend/runs/*` are git-ignored). Share them via the team Drive or WhatsApp link in the board post, with a sha256.
- **Check what you're running at any time:** `make data-status` and `curl localhost:8000/api/health` (`data_source`).
