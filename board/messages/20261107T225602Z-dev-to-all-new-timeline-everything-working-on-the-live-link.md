---
id: 20261107T225602Z-dev-to-all-new-timeline-everything-working-on-the-live-link
from: dev
to: all
type: fyi
status: open
issue: 
created: 2026-11-07T22:56Z
---
# NEW TIMELINE: everything working on the live link by 09:00

Everyone stays up. Full table: docs/09-build-plan.md. GitHub milestones updated with times.

- 00:00 M0: everyone running locally; Dev sends keys to Jin; real snapshot download starts (switch 1 when Jin posts)
- 02:30 M1: spine works end to end on one machine; config frozen (eval-freeze tag, switch 3)
- 03:00 4-month agent run (~1 h) + --no-agents baseline; Jin does a deploy DRY RUN meanwhile
- 04:15 recorded runs posted (switch 4)
- 06:30 second deploy with recorded runs
- 07:00 FEATURE FREEZE (unstarted feature issues dropped)
- 08:00 final deploy; 08:30–09:00 full smoke test → M2 DONE
- 09:00–11:00 video (from the link), deck, README, checklist
- 12:20 submit (deadline 12:30)

End goal: ONE public link with demo + live mode, and the demo never waits on an API call. New MVP issue #78 (Jin): demo replays the recorded run with LLM_MODE=replay; live mode reads cache; live agent runs are async.

## Replies
