# Agent message board

A git-based inbox where our coding agents (and humans) leave each other **questions, handoffs, missing-piece reports, blockers and contract changes**. WhatsApp is for pings; this is the written record a fresh agent can act on.

## Names

`dev` (@Prittstick22, agents) · `cem` (@cempnrbs, engine/sim) · `jin` (@JCYuhei, data/API/deploy) · `mo` (@MLouchini, frontend) · `all`

## Message types

| Type | Use when |
|---|---|
| `question` | You need a decision or clarification from someone |
| `handoff` | You finished something another person builds on (say exactly how to use it) |
| `missing` | Something you need from another area doesn't exist yet (say the function/field/endpoint and its shape) |
| `blocker` | You can't continue; also ping on WhatsApp |
| `contract-change` | You changed (or need to change) an API/event/model shape in `docs/04-api-contracts.md` |
| `fyi` | Useful info, no action needed |

## Commands (`scripts/board.py`, no dependencies)

```bash
git pull
python scripts/board.py list --to jin --open           # what's waiting for jin (+ "all")
python scripts/board.py list --open                    # everything open
python scripts/board.py show board/messages/<file>.md
python scripts/board.py new --from mo --to jin --type missing --issue 21 \
    --title "Need GET /api/portfolio/pnl" --body "Shape per 04 §2; mock works, real 404s."
python scripts/board.py reply board/messages/<file>.md --from jin --body "Merged in #34, deployed."
python scripts/board.py resolve board/messages/<file>.md --from mo
git add board && git commit -m "board: <title>" && git push   # board-only commits may go to main
```

`--body -` reads the body from stdin, so agents can pipe longer markdown in.

## File format (`board/messages/<UTC timestamp>-<from>-to-<to>-<slug>.md`)

```markdown
---
id: 20261107T2130Z-mo-to-jin-need-pnl-endpoint
from: mo
to: jin
type: missing
status: open            # open | answered | resolved
issue: 21
created: 2026-11-07T21:30Z
---
# Need GET /api/portfolio/pnl

<what you need, why, exact names/paths/shapes, deadline>

## Replies
### jin · 2026-11-07T21:52Z
Merged in #34.
```

## Etiquette for agents

- **Check the board at session start and before every PR.**
- One topic per message. Link the issue/PR. Give file paths and exact names.
- Answer messages addressed to your human within your session, or tell your human to.
- Don't edit another person's files to unblock yourself. Post `missing`, stub behind the agreed interface, move on.
- Resolve messages when they're done, so `--open` stays short.
