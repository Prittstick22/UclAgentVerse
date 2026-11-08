---
id: 20261108T005344Z-dev-to-all-new-agents-md-rule-9-keep-the-organisers-kit-out
from: dev
to: all
type: fyi
status: open
issue: 
created: 2026-11-08T00:53Z
---
# New AGENTS.md rule 9: keep the organisers' kit out of our code

AGENTS.md §3 has a new rule 9 (PR #99). Please tell your agents.

- The organisers' AgentVerse finance kit stays **outside** the repo at `../agentverse/` (gitignored). Only `.agents/skills/` holds copies of its skills (finance-test, review-and-push).
- **Never** write these in our code, even in comments: imports of the kit's `bench` / `testbed` / `core`, `answers.jsonl`, `SEED-REVEAL`, `AGENTVERSE_CHALLENGE`, `data.binance.vision`. The hidden-test provenance scan reads every .py/.js/.ts file in our repo and lists any match as a warning in our judging report. Markdown isn't scanned.
- Checked just now: our code has **no** matches. Details: docs/finance-kit.md.
- 'Keep it small' is now rule 10.

## Replies
