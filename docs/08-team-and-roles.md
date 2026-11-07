# 08 · Team and roles

Four people, four coding agents. Everyone owns an area, and **everyone picks up anything when ahead**: check the issue board for unassigned `tier:1` issues first.

| Person | GitHub | Coding agent | Primary area | Also on |
|---|---|---|---|---|
| **Dev** | @Prittstick22 | Claude | **Gemini agents:** LLM wrapper, supervisor, roles/prompts, tools, assurance gate, guard, chat, memory/learning. **Plus all paid/external APIs:** accounts, payment, keys, provider adapters and the provider smoke test (#3, #54–#57) | **All deploys** (DigitalOcean); pitch content + script |
| **Cem** | @cempnrbs | GPT + Claude | **Engine + simulator:** risk, correlation, optimiser, checker, ledger, metrics, backtest, exposure, monitors/triggers, benchmarks, evaluation numbers | Eval slide |
| **Jin** | @JCYuhei | Claude | **Data + platform:** snapshot fetch (using Dev's verified adapters), DataGateway, clock, events/SSE, API routes, quiz scoring, live mode + scheduler, CI | **Deck slides** (built in parallel from 03:00); data sanity |
| **Mo** | @MLouchini | GPT | **Frontend:** every screen, charts, agent tree, gate strip, correlation lattice, mock mode | **Demo video** in parallel: shot list 02:30, rough cut 07:30, final 10:30 |

## Interfaces (who depends on whom)

| From → to | Contract | Where |
|---|---|---|
| Mo ← Jin/Cem/Dev | REST + SSE shapes | `docs/04-api-contracts.md`, `frontend/src/lib/types.ts`, `fixtures/` |
| Dev ← Cem | Engine functions agents call as tools | 04 §4, `engine/*.py` signatures |
| Dev ← Jin | `DataGateway`, `events.emit` | 04 §4 |
| Jin ← Dev | Provider keys (privately) + verified adapters in `data/adapters/` | #54, #55 |
| Cem ← Jin | Gateway, clock, events for the sim loop | 04 §4 |
| Cem ← Dev | `supervisor.start(kind, trigger, as_of) -> RunResult` called by the sim | `agents/supervisor.py` |
| Jin ← Cem/Dev | API handlers call engine/supervisor | `api/*.py` |

**Rule:** if you need something from another area, don't edit their files. Post `--type missing` on the board, ping on WhatsApp, and stub it on your side behind the same interface.

## Handoffs that unblock others (do these first)

1. **Jin → all:** synthetic snapshot + gateway + events working (`make synth && pytest`). *Target 22:00.*
2. **Cem → Dev:** `optimise()` + `check_proposal()` callable with the real signature (even if naive). *Target 23:00.*
3. **Dev → Cem:** `supervisor.start()` returns a fake `RunResult` in `LLM_MODE=fake`, so the sim loop can integrate. *Target 23:00.*
4. **Jin → Mo:** real `/api/health`, `/api/profile/*`, `/api/runs/{id}/events` (SSE). Until then Mo uses mock mode. *Target 00:00.*
5. **Dev → all:** deploy dry run on the DigitalOcean droplet with the real HTTPS URL. *Target 04:15.*

## Rituals

- **Stand-up on WhatsApp** at 22:00, 00:00, 03:00 (before the batch), 07:00, 09:00 (freeze). Each person: done / doing / blocked.
- **Board check:** every coding-agent session starts with `python scripts/board.py list --to <name> --open`.
- **Merging:** small PRs, CI green, merge. Contract changes must have a board post.
- **Sleep shifts** while the overnight batch runs: Dev + Mo 03:30–06:00; Cem + Jin 06:00–08:00 (adjust on the night).
