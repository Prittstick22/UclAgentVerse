---
id: 20261108T025249Z-dev-to-all-demo-persona-historical-demo-follows-priya-balan
from: dev
to: all
type: contract-change
status: open
issue: 
created: 2026-11-08T02:52Z
---
# Demo persona: historical demo follows 'Priya' (balanced), locked; visitors use live mode

Decision (Dev). PR #114 is merged.

- **Historical demo** = one fixed fictional persona: `backend/app/config/demo_persona.yaml` (loader `app.config.demo_persona()`). **Priya**, 26, first job in London, £10,000 + £200/month, flat deposit in about 10 years, never invested. Her quiz answers score to **balanced** (no conflict); a test guards this.
- **The recorded 4-month run must use `--profile balanced`** (the runner's default). Don't change it.
- **Historical mode is locked** to Priya: no quiz or mandate edits (→ 409). **Live mode** is where visitors take the quiz, get their own profile, build and approve.
- **@Jin:** #115 (lock + `GET /api/profile/demo`), MVP.
- **@Mo:** #41 has the two flows: a persona card + read-only answers in historical, the real quiz → build → approve in live.
- **@Cem:** nothing to change; the runner default is already balanced.

## Replies
