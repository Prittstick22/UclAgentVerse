# Dev's agent handoff

Start with `AGENTS.md`, then read these in order:

1. [Current state](STATE.md) — what is working, what is shared and what remains.
2. [Runbook](RUNBOOK.md) — startup, tests and recovery.
3. [Next-agent prompt](NEXT_AGENT_PROMPT.md) — copy the fenced text into the next agent.

The completed recording is bundled in Git. Anyone with a clone can run `python scripts/demo.py --setup`, then choose Demo at http://127.0.0.1:8000/. No provider keys are needed. First setup installs software dependencies; playback is offline.

Detailed session history remains in [docs/HANDOVER-dev.md](../docs/HANDOVER-dev.md). This folder is the concise current handoff; do not treat older, superseded "next steps" in that long history as new authorisation for paid runs or deployment.
