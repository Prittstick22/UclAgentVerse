# AGENTS.md: rules for AI coding agents working in this repo

Read this fully before you write code. It applies to every coding agent (Claude Code, Codex/GPT, Gemini CLI, Cursor, …). Humans: this is also the shortest accurate summary of how we work.

## 1. What we're building (60 seconds)

An AI investment team for first-time UK investors.
- A quiz produces a mandate.
- Supervised Gemini agents build a **paper** portfolio (ETFs, bond ETFs, a few stocks).
- A simulator replays Nov 2025 → Nov 2026 day by day, with fortnightly reviews plus 5% triggers.
- A change is only proposed after an assurance gate (evidence, numbers, critic, compliance, QA) and needs user approval.
- Live mode runs the same code on today's data.

Full spec: `docs/01-project-spec.md`. How it works end to end: `docs/03-how-it-works.md`.

**Deadline:** feature freeze **Sun 09:00**, demo and deck **11:00**, submit **12:20** (hard deadline 13:00 London).

## 2. Who you are working for

Each human runs their own agent. Work mostly inside your human's area, but anyone may pick up any issue when ahead.

| Human | GitHub | Area | Folders they own |
|---|---|---|---|
| Dev | @Prittstick22 | Gemini agents; all paid/external API accounts, keys and provider adapters | `backend/app/agents/`, `backend/app/data/adapters/`, `backend/scripts/check_providers.py` |
| Cem | @cempnrbs | Engine + simulator | `backend/app/engine/`, `backend/app/sim/`, `backend/app/monitors/` |
| Jin | @JCYuhei | Data, API, live mode, deploy | `backend/app/data/` (except adapters), `backend/app/api/`, `backend/app/core/`, `backend/app/profile/`, `backend/scripts/`, `Dockerfile`, `.github/` |
| Mo | @MLouchini | Frontend | `frontend/` |

Shared and contract files (change only with a board message, §5): `docs/04-api-contracts.md`, `backend/app/core/events.py`, `backend/app/schemas.py`, `frontend/src/lib/types.ts`, `backend/app/config/*`, `fixtures/*`.

## 3. Non-negotiable rules

1. **The clock is the firewall.** Never read data except through `DataGateway` (`backend/app/data/gateway.py`). Never call `datetime.now()` in business logic; use `clock.now()`. In historical mode nothing may see data dated after `as_of`. This is how we avoid look-ahead bias, and it is one of our judged controls.
2. **Agents propose; code decides the numbers.** Weights, costs, exposures, risk and limit checks live in `backend/app/engine/` as deterministic Python. Agent code may *call* engine functions but must not reimplement or override them. No LLM output is ever trusted as a number.
3. **Everything is an event.** Any agent step, tool call, check, decision or trade emits a typed event via `core.events.emit(...)`. Tool results are emitted by the tool wrapper, never by the model. Event shapes are defined in `docs/04-api-contracts.md`; if you need a new type, add it there *and* in `core/events.py` *and* in `frontend/src/lib/types.ts`, then post on the board.
4. **Contracts first.** Don't change an API response or event shape silently. Update `docs/04-api-contracts.md`, the Pydantic models and the TS types in the same PR, and post a `contract-change` message on the board.
5. **Config is frozen before evaluation.** Values in `backend/app/config/*.yaml` are fixed before the full-year run. Don't tune them on simulation-year results. If you think a value is wrong, post on the board.
6. **No secrets in git.** Keys go in `.env` (git-ignored) (on the DigitalOcean droplet only). Never print keys in logs or events.
7. **No real personal or financial data.** Profiles and amounts are fictional. Paper trading only. Synthetic data must be labelled `synthetic` in its source field and in the UI.
8. **Offline-friendly.** Code must run with `LLM_MODE=fake` (no Gemini key) and with the synthetic snapshot (no data keys). Tests must not hit the network.
9. **Keep it small.** We have hours, not weeks. Prefer the simplest thing that satisfies the issue's acceptance criteria. No new frameworks without a board message.

## 4. How to work an issue

1. Pick an issue assigned to (or labelled for) your human: `gh issue list --label owner:<name>`. Comment "taking this" if it's unassigned.
2. Branch from `main`: `git checkout -b <name>/<issue-number>-<short-slug>`, e.g. `cem/12-optimiser`.
3. Read the issue's **How** and **Acceptance criteria**, plus the linked doc section.
4. Write the code **and** tests. Backend: `cd backend && pytest -q` must pass. Frontend: `cd frontend && npm run build` must pass.
5. Commit with a conventional message referencing the issue: `feat(engine): CVXPY optimiser with caps (#12)`.
6. Open a PR to `main` with `Closes #12`, and tick the acceptance criteria in the description. Small PRs; merge fast once CI is green. Anyone can review; at night, self-merge when CI is green and the change stays in your area.
7. If you're blocked for more than 15 minutes, post on the board (§5) and tell your human to ping on WhatsApp.

**Definition of done:** acceptance criteria met, tests pass, CI green, docs updated if behaviour or contracts changed, no TODOs left in critical paths without an issue number.

## 5. Message board for agents (`board/`)

A shared inbox in git so agents can leave each other handoffs, questions and missing-piece reports. Humans also ping each other on WhatsApp; the board is the written record.

- **At the start of every session, and before opening a PR:** `git pull` then `python scripts/board.py list --to <your-human> --open`. Read and act on anything addressed to you or to `all`.
- **To post:** `python scripts/board.py new --from <you> --to <name|all> --type <question|handoff|missing|blocker|contract-change|fyi> --title "..." [--issue 12]`. This creates `board/messages/<timestamp>-<from>-to-<to>-<slug>.md`. Fill in the body, then commit and push it on its own (`git add board && git commit -m "board: ..." && git push`) so others see it fast. Board-only commits may go straight to `main`.
- **To reply:** `python scripts/board.py reply <file> --from <you>` appends a reply section. **To close:** `python scripts/board.py resolve <file>`.
- Write so a fresh agent with no context can act: what you need, why, file paths, exact function or field names, and the deadline.
- Full protocol: [`board/README.md`](board/README.md).

## 6. Repo map

```
backend/app/
  main.py            FastAPI app, routers, serves built frontend from /
  settings.py        env vars (pydantic-settings)
  schemas.py         shared Pydantic models (Mandate, Portfolio, Proposal, …)
  core/              clock, events (bus + SQLite log + SSE), db
  data/              DataGateway (as_of firewall), snapshot loader, provider adapters
  engine/            risk (Ledoit-Wolf, correlation), optimiser (CVXPY), checker, ledger, metrics, backtest, exposure
  profile/           quiz questions + scoring → mandate
  agents/            llm wrapper (Gemini / fake), supervisor (spawn limits), roles, tools, gate, guard, prompts/
  monitors/          trigger rules, cooldowns, monitor templates
  sim/               day-by-day runner, benchmarks, approvals
  api/               HTTP routes
  config/            policy.yaml, params.yaml, agents.yaml, catalogue.json
backend/scripts/     fetch_snapshot.py, make_synthetic_snapshot.py, make_fixtures.py
backend/tests/
frontend/src/        screens/, components/, lib/ (types, api client, SSE, mock mode)
fixtures/            sample events + API responses (generated by make_fixtures.py)
docs/                spec, architecture, contracts, plans
board/               agent message board
```

## 7. Commands

```bash
make setup         # backend venv + frontend npm install
make synth         # synthetic snapshot for dev
make test          # backend pytest
make dev-api       # uvicorn on :8000
make dev-web       # vite on :5173
make fixtures      # regenerate fixtures/ from backend schemas
make build         # docker build
```

## 8. Style

- **Python:** 3.11+, type hints, Pydantic v2 models at module boundaries, `ruff` formatting, no global mutable state except the app container in `main.py`.
- **TypeScript:** strict mode, function components, Tailwind classes, no `any` in `lib/types.ts`.
- **User-facing copy:** plain English, £ not %, where possible. No promises of returns. Every simulated or backtested number is labelled.
