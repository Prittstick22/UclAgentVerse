> **README prototype — not the final submission.** Keep this file separate until
> the demo, recording, video and deck are final. Existing README remains unchanged.
> Relative links are written for the repository root so this can later become README.md.

# UclAgentVerse

**An AI investment team for first-time UK investors: understandable proposals,
visible evidence, and a human decision before a paper trade.**

Built for the UCL AgentVerse Hackathon 2026, Finance track.

| Try or review | Link / status |
|---|---|
| Hosted demo | FINAL LINK TO CONFIRM. [Deployment dry-run address](https://165-22-115-152.sslip.io); not certified here as the final recorded demo. |
| Demo video (under 3 minutes) | ADD FINAL VIDEO LINK |
| Pitch deck | ADD FINAL DECK / PDF LINK |
| Code | [Team repository](https://github.com/Prittstick22/UclAgentVerse) |

Public historical playback is intended to need no passcode or external API call.
Protected live agent requests may ask for the demo passcode; the final submission
must say how judges receive it. Do not put credentials in this README.

No promise of returns.

## What it does

First-time UK investors need a way to understand portfolio choices and what a
proposed change means for them. Our prototype connects a risk quiz and mandate
to a supervised agent team, deterministic portfolio calculations, and an approval gate.

- **Profile:** live-mode visitors answer the quiz and review their mandate.
- **Build:** agents research ETFs, bond ETFs and selected stocks; code calculates
  weights, risk, exposures, costs and limits.
- **Monitor:** fortnightly reviews and configured triggers investigate changes.
- **Decide:** a proposal shows its evidence, checks, uncertainties and paper
  orders. A live visitor must approve before execution.

Historical mode follows **Priya**, a fixed fictional balanced investor. It is
not the visitor's live portfolio. Recorded simulation approvals can follow a
disclosed batch policy; those are not approvals from a real customer.

## Try the demo

1. Open the hosted link and select the historical demo.
2. Inspect Priya's mandate and portfolio; use the timeline to replay the recorded activity.
3. Open a proposal or decision card and inspect its evidence and assurance checks.
4. Inspect paper rebalances and performance comparisons, retaining their dates and labels.
5. Switch to current paper markets to explore a separate visitor profile.

**Final-demo check pending:** verify these steps against the deployed build and
the completed recording before submission. Do not claim instant playback from
an unverified or incomplete recording. Live pages read cached data; a new live
agent investigation is asynchronous and may take time.

## Run locally without API keys

Use a **fresh checkout**, Python 3.12 (the CI runtime), Node.js 22 LTS and npm.
Run from the repository root. Dependency installation needs internet; after
installation, this walkthrough uses generated synthetic data and deterministic
fake agent outputs, not paid services or the canonical recorded agent run.

### macOS / Linux — five commands

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e './backend[dev]'
.venv/bin/python backend/scripts/make_synthetic_snapshot.py --out backend/data/readme-synthetic
env -u RECORDED_RUN APP_MODE=historical LLM_MODE=fake PUBLIC_DEMO=0 SNAPSHOT_DIR="$PWD/backend/data/readme-synthetic" STATE_DB="$PWD/backend/readme-state.sqlite" .venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
npm --prefix frontend ci && VITE_MOCK=0 npm --prefix frontend run dev -- --host 127.0.0.1
```

Command 4 stays running: execute command 5 in a **second terminal** at the same
repository root. Then open http://localhost:5173. The API health endpoint is
http://127.0.0.1:8000/api/health; expect `llm_mode: fake` and a synthetic data source.

### Windows PowerShell — five commands

```powershell
py -3.12 -m venv .venv
& ./.venv/test/Scripts/python.exe -m pip install -e './backend[dev]'
& ./.venv/test/Scripts/python.exe backend/scripts/make_synthetic_snapshot.py --out backend/data/readme-synthetic
Remove-Item Env:RECORDED_RUN -ErrorAction SilentlyContinue; $env:APP_MODE='historical'; $env:LLM_MODE='fake'; $env:PUBLIC_DEMO='0'; $env:SNAPSHOT_DIR=(Join-Path $PWD 'backend/data/readme-synthetic'); $env:STATE_DB=(Join-Path $PWD 'backend/readme-state.sqlite'); & ./.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
npm --prefix frontend ci; if ($LASTEXITCODE -eq 0) { $env:VITE_MOCK='0'; npm --prefix frontend run dev -- --host 127.0.0.1 }
```

Run command 5 in a second PowerShell terminal at the repository root while the
API stays running. These commands use separate local snapshot/state paths and
do not overwrite the default market snapshot. `RECORDED_RUN` must be unset for
this walkthrough; remove a nonempty value from any existing root/backend `.env`
if adapting the instructions to an existing checkout. No `.env` is required for
a fresh checkout. Stop each server with Ctrl+C.

Choose the historical demo for the offline walkthrough. Synthetic prices and
fake reasoning are development aids, **not evidence of investment performance**.
To replay the canonical historical run, obtain the approved snapshot and complete
SQLite recording from the team; see [recorded-deployment instructions](docs/12-hosting-and-deploy.md).
Do not switch to paid/live providers as part of the no-key walkthrough.

## Models and verification loop

Current code defaults: `gemini-4-argon` for deep roles and `gemini-3.8-flash` for
fast roles, selected through role routing. Environment settings can override
both. Earlier all-Argon recordings remain all-Argon evidence; **confirm the exact
model IDs from the final recording before publishing this section**.
`LLM_MODE=fake` does not call either model.

**Dated evidence → agent proposal → deterministic calculations → assurance gate
→ human approval → paper fill.**

The gate covers injection handling, evidence, numbers, mandate limits, critic,
compliance and QA. Agents propose; code determines investment numbers. Historical
market evidence is accessed through a dated gateway capped at the simulation
clock, and the event log exposes the reasoning steps and checks. See the
[agent system](docs/05-agent-system.md) and [API/event contracts](docs/04-api-contracts.md).

## Evaluation and limitations

The planned historical replay window is **7 July–6 November 2026**. Keep
performance figures labelled simulated/backtested and identify their snapshot,
recording, model settings, costs and approval policy.

- **Four-month portfolio comparison:** ADD VERIFIED RESULTS LINK and summary
  comparing the agent system, engine-only baseline and investment baselines.
  Do not substitute fixture outputs or synthetic development returns.
- **Organiser challenge:** the existing [real-market report](eval/finance-kit/challenge-real-markets/REPORT.md)
  reports 14 wins, 14 losses and 32 ties versus buy-and-hold on 60 anonymised
  price paths; its verdict is not distinguishable from buy-and-hold. This tests
  the deterministic adapter, not the complete Gemini workflow. No investment
  edge is claimed. See [protocol, synthetic results and rerun disclosures](docs/finance-kit.md).

Organisers: please run the finance-kit challenge with `--pack markets` and
`--pack real-markets`. Adapter command (from an environment with backend
dependencies installed): `cd backend && python -m app.eval.finance_kit_adapter`.
Cashflow and transaction-monitoring tasks are outside this product.

## Checks

From `backend/`, using the configured Python environment: `python -m pytest -q`.
From `frontend/`: `npm test` and `npm run build`.
CI runs backend tests plus frontend tests and the production build. Do not pin
a test count here; use the final submission commit's CI result.

## Data sources and terms

Market inputs include EODHD, Finnhub and SEC EDGAR; instrument reference evidence
links to issuer documents. Development uses explicitly labelled synthetic prices
and text; the organiser real-market evaluation uses anonymised Binance windows.
Provider access is not a blanket public-display or redistribution licence.
See [data sources, terms and synthetic-data disclosure](docs/DATA_SOURCES.md).

## Team

| Person | GitHub | Area |
|---|---|---|
| Dev | [@Prittstick22](https://github.com/Prittstick22) | Agents, provider accounts/adapters, deployment, pitch content |
| Cem | [@cempnrbs](https://github.com/cempnrbs) | Portfolio engine, simulator and evaluation |
| Jin | [@JCYuhei](https://github.com/JCYuhei) | Data, API, live mode and deck slides |
| Mo | [@MLouchini](https://github.com/MLouchini) | Frontend and demo video |

More detail: [how it works](docs/03-how-it-works.md) ·
[architecture](docs/02-architecture.md) · [documentation index](docs/README.md).

---

### Before promoting this prototype to README.md

- Replace the demo, video, deck and portfolio-evaluation placeholders; check every link.
- Smoke-test the hosted walkthrough, no-key recorded playback and passcode handoff.
- Rehearse local setup in a fresh checkout on the documented platforms; these
  prototype instructions have been checked against source, not clean-installed on both OSes.
- Confirm final recording models, data provenance, permissions and result labels.
- Remove draft/editor notes and this checklist; retain useful limitations.
- Keep #70 open until the final README acceptance criteria actually pass.
