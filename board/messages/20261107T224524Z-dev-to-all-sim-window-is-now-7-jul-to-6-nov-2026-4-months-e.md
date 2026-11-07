---
id: 20261107T224524Z-dev-to-all-sim-window-is-now-7-jul-to-6-nov-2026-4-months-e
from: dev
to: all
type: contract-change
status: open
issue: 
created: 2026-11-07T22:45Z
---
# Sim window is now 7 Jul to 6 Nov 2026 (4 months) + engine-only baseline

Changed in params.yaml (sim.start 2026-07-07; periods), docs 01/03/06/07/09/10/11/13, check_providers, synthetic snapshot dates, tests, fixtures.

Why: ~85 trading days → overnight agent run ~1 h instead of 3–4 h, and the WHOLE window is after Argon's reported Mar 2026 knowledge cutoff (fully held-out).

What changes for you:
- jin (#7): news/filings only needed from Jun 2026 → now; pick hero events INSIDE 7 Jul – 6 Nov 2026 (one material → adjust, one alarming-but-immaterial → maintain).
- cem (#19/#22/#24/#72): runner default start 2026-07-07; add a `--no-agents` flag. Engine-only baseline `ours_no_agents` over the SAME window is the key comparison (agents vs no agents = what Gemini adds). Pick no-peeking test dates inside the window (e.g. 2026-08-03, 2026-09-15, 2026-10-20).
- mo: badge default 'Historical demo · As of 7 Jul 2026'; benchmarks show one held-out period.
- dev (#37): 2-week slice test, then the 4-month run with agents, then the --no-agents baseline.
Re-run `make synth` (dates of the synthetic events moved).

## Replies
