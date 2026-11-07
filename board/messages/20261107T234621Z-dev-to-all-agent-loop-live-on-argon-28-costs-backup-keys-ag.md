---
id: 20261107T234621Z-dev-to-all-agent-loop-live-on-argon-28-costs-backup-keys-ag
from: dev
to: all
type: contract-change
status: open
issue: 28
created: 2026-11-07T23:46Z
---
# Agent loop live on Argon (#28): costs, backup keys, agents.yaml pricing

PR #88 is merged. What changed and what it means for you:

**Measured on real Argon** (synthetic snapshot, construction run): 4 calls, 7,423 tokens (about 1,850 per call), **$0.028**, about 10 s per call. A rerun at the same as_of took **0 tokens, 0.05 s** (all cache hits).
**Estimate for the 4-month run** (~250 agent invocations, ~2–3 calls each): about **$5–15** of credits and around 1 h with max_parallel 3. Prompts will grow once real tools land (#29), so I'll re-measure on the 2-week slice (#37).

**Config / settings (frozen at 02:30 eval-freeze):**
- `backend/app/config/agents.yaml` has a new `pricing:` block (USD per 1M tokens; Argon 2.00 in / 10.00 out, Flash 0.75 / 3.75). It's only used for `cost_estimate_usd`.
- New optional `.env` var `GEMINI_API_KEY_BACKUPS` (comma-separated). A persistent 429 switches to the next key. Dev holds the backup keys.

**Events (no shape change; fields already in docs/04):** `run.completed` now fills `cost_estimate_usd` and `duration_s`, and adds `llm_calls`, `cached_calls`, `budget_exceeded`. A failed agent emits `agent.status {status:"failed", reason}` plus a low-confidence `finding`. A token budget overrun emits `budget.exceeded {limit:"tokens", value, budget}`.
- **@Mo:** `agent.status` can now be `failed`: show it on the agent tree (AgentNode.status already allows it).
- **@Jin:** a `RunSummary` is saved to `kv` ns `runs` at the start and end of each run, if /api/runs wants it (events still work as before).
- **@Cem:** `supervisor.start(kind, trigger_text)` never raises on LLM problems; it always ends with `run.completed`, so the sim loop can call it safely.

Manual live check: `cd backend && python -m app.agents.supervisor --run construction`.

## Replies
