---
id: 20261107T213706Z-dev-to-all-when-to-switch-data-4-switch-moments
from: dev
to: all
type: fyi
status: open
issue: 
created: 2026-11-07T21:37Z
---
# When to switch data: 4 switch moments

Each person's local state.sqlite is throwaway and differs per person; that's fine. Shared data is FILES, switched at 4 announced moments (full table in docs/13-dev-workflow.md, 'Data sharing'):

1. ~00:00 Jin posts 'real snapshot ready' with a link + sha256 → replace backend/data/snapshot/, delete backend/state.sqlite, restart, run `make data-status` (label eodhd, sha matches). Never run `make synth` after this.
2. ~01:30 Dev pushes fixtures from a real agent run → git pull.
3. 02:30 eval-freeze tag → config/* frozen.
4. ~07:00 recorded year (runs/year.sqlite) posted → everyone uses that file; it's the single source of truth for replay, eval and the deployed demo. Nobody reruns the year.

Don't switch before the post; switch as soon as you see it. Big files go via Drive/WhatsApp, never git.

## Replies
