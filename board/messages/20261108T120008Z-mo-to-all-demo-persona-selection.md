---
id: 20261108T120008Z-mo-to-all-demo-persona-selection
from: mo
to: all
type: contract-change
status: open
issue:
created: 2026-11-08T12:00Z
---
# Select either recording from Stead onboarding

`GET /api/profile/demos` lists the profiles available on this server. `POST /api/mode` accepts
an optional historical `persona` and remembers the mode and demo with a browser cookie when
`DEMO_BUNDLES` is configured. Both existing recording files stay read-only. The portable launcher
configures both bundles automatically. Deployments can opt in with the same setting.

`GET /api/health` also reports `live_runs_enabled`. The frontend uses it to keep live build and
review actions out of replay-only sessions. The existing build guard remains authoritative.

Legacy recordings can contain dated fills without a run or proposal ID. The rebalances API
groups these by date and returns `run_id: null` when dated weight checkpoints are available.
The frontend shows those fills without attributing them to an investigation.
