# CLAUDE.md

@AGENTS.md

The file above (`AGENTS.md`) contains all the rules and is shared with the GPT/Codex agents on the team. Key points for Claude Code sessions:

- **At the start of every session:** run `git pull`, then `python scripts/board.py list --to <your human> --open`, and act on messages addressed to you. Your human is whoever is running this session: dev, cem, jin or mo.
- **Before writing code:** read the GitHub issue you're working on (`gh issue view <n>`) and the doc section it links.
- **Never break these:** all data reads through `DataGateway` with `as_of`; all numbers from `backend/app/engine/`; emit events for every step; contract changes need a board post.
- **Before a PR:** `cd backend && pytest -q` and/or `cd frontend && npm run build`.
- **If you're blocked or something is missing from another person's area:** post on the board (`--type missing` or `--type blocker`) instead of editing their files.
