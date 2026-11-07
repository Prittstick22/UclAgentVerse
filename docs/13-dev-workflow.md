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
| `EODHD_API_KEY`, `FINNHUB_API_KEY`, `ALPHAVANTAGE_API_KEY`, `ALPACA_KEY_ID`, `ALPACA_SECRET_KEY` | — | Data providers |
| `EDGAR_USER_AGENT` | `UclAgentVerse team <team-email>` | SEC asks for a contact |
| `SNAPSHOT_DIR` | `backend/data/snapshot` | Snapshot location |
| `STATE_DB` | `backend/state.sqlite` | Events, ledger, memory, LLM cache |
| `PUBLIC_DEMO`, `DEMO_PASSCODE`, `TASK_SECRET`, `DAILY_LLM_BUDGET_USD` | `0`, —, —, `20` | Deploy safety |

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
