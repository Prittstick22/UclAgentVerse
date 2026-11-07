# UclAgentVerse

**An AI investment team for first-time UK investors.** UCL AgentVerse Hackathon 2026, Finance track (Google DeepMind, Gemini Argon).

> Start investing in five minutes. Then forget about it. We'll tell you when something needs your decision.

You answer a short quiz. A supervised team of Gemini agents builds a **paper** portfolio of ETFs, bond ETFs and a few stocks, then keeps watching it. Fortnightly reviews and 5% triggers run in the background. When something needs a decision, you get one plain-English card that shows its working, and that working has already been checked by separate reviewer agents.

A historical mode replays **7 Jul → 6 Nov 2026** day by day, entirely after the model's knowledge cutoff, and every day sees only data up to that day. Live mode runs the same system on today's data.

Paper trading only. No real money, accounts or personal financial data. Not financial advice.

## Start here

| If you are… | Read |
|---|---|
| Anyone, first time | [`docs/01-project-spec.md`](docs/01-project-spec.md) → [`docs/03-how-it-works.md`](docs/03-how-it-works.md) |
| An AI coding agent | [`AGENTS.md`](AGENTS.md) (Claude also gets [`CLAUDE.md`](CLAUDE.md)) |
| Working on the frontend | [`docs/04-api-contracts.md`](docs/04-api-contracts.md), [`frontend/README.md`](frontend/README.md) |
| Working on agents | [`docs/05-agent-system.md`](docs/05-agent-system.md) |
| Working on engine / sim | [`docs/07-engine-and-config.md`](docs/07-engine-and-config.md) |
| Working on data / API / deploy | [`docs/06-data-plan.md`](docs/06-data-plan.md), [`docs/12-hosting-and-deploy.md`](docs/12-hosting-and-deploy.md) |
| Wondering who does what | [`docs/08-team-and-roles.md`](docs/08-team-and-roles.md), [`docs/09-build-plan.md`](docs/09-build-plan.md) |

All docs: [`docs/README.md`](docs/README.md). Agent-to-agent questions and handoffs: [`board/`](board/README.md). Issues are tagged `mvp` (do first) or `feature`.

## Team

| Person | GitHub | Owns |
|---|---|---|
| Dev | [@Prittstick22](https://github.com/Prittstick22) | Gemini agents, paid/external APIs and keys, finance kit, benchmarks, deck and pitch |
| Cem | [@cempnrbs](https://github.com/cempnrbs) | Engine and simulator: risk, optimiser, forecast, checker, ledger, triggers, evaluation |
| Jin | [@JCYuhei](https://github.com/JCYuhei) | Data snapshot, API, event stream, live mode, DigitalOcean deploy |
| Mo | [@MLouchini](https://github.com/MLouchini) | Frontend: every screen, charts, demo video |

## Quickstart (works offline, no keys)

```bash
# Backend (Python 3.11+)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python scripts/make_synthetic_snapshot.py   # SYNTHETIC dev data until the real snapshot lands
pytest -q
uvicorn app.main:app --reload --port 8000    # http://localhost:8000/api/health

# Frontend (Node 20+)
cd frontend
npm install
npm run dev                                  # http://localhost:5173 (mock mode by default)
```

Copy `.env.example` to `.env` at the repo root and fill in keys. **Never commit `.env`.** Everything runs without keys in `LLM_MODE=fake` (deterministic canned agent outputs) on the synthetic snapshot.

## Repo map

```
backend/            FastAPI app, engine, simulator, agents, data gateway (Python)
  app/config/       policy.yaml, params.yaml, agents.yaml, catalogue.json, frozen before the eval run
  scripts/          fetch_snapshot.py, make_synthetic_snapshot.py, make_fixtures.py, check_providers.py
  tests/            pytest (incl. the judged controls)
frontend/           React + TypeScript + Vite + Tailwind
fixtures/           Shared sample events / API responses (frontend mock mode)
docs/               Everything about the project
board/              Message board for our coding agents
Dockerfile, docker-compose.yml, Caddyfile   One container + HTTPS on a DigitalOcean droplet
```
