# Current state — 8 November 2026

## Working and shared

The complete Priya balanced demo covers **7 July–6 November 2026**, 89 trading days. It contains an initial portfolio construction and eight reviews; all eight chose maintain. There are four ETF holdings and 14 fills including contribution investing. No trades were forced for presentation.

Capture used **gemini-4-argon** for deep/lead roles and **gemini-3.8-flash** for fast roles: 48 calls, 181,598 tokens, estimated **$0.4335445**, **510.17 seconds**. All seven construction gates passed. Final simulated NAV was **£10,918.28 from £10,800 contributed**; do not describe the increase from £10,000 as profit.

The portable archive and checksum manifest are in `demo/`. It contains only the simulation SQLite and clean input snapshot. It excludes `.env`, credentials, Live state, local logs, user paths and organiser files. Dev explicitly confirmed public distribution permission for its included EODHD/Finnhub data and article text. This confirmation is scoped to this frozen bundle.

Recording SHA256: `53ff18a27d31fb24344855e25936d99e3973d79f55705d16c21064bd654086d0`.

Validated: all 54 evidence IDs; dates and mode isolation; full saved playback; zero provider calls during replay; unchanged recording hash; refresh; asset price graph; populated correlation lattice/matrix/split view; five comparison rows; Live quiz to investment-plan review, stopping before Build.

PR #137 fixed evidence lookup/versioning. PR #138 added capture safeguards, unknown constituent handling and UTF-8 snapshot loading. PR #139 (merged as 144a4a7, both CI jobs green) adds the public bundle, no-key launcher and this handoff. All 454 backend tests and 7 frontend tests/build passed. Fresh-clone --setup/start was verified with no .env on port 8012: UI assets, all 54 evidence IDs, full replay, mode separation and explicit refusal of new Live investigations passed. The source recording hash stayed unchanged; the temporary test server was then stopped.

## Current limits

- No verified historical ETF constituent lists are bundled. Ownership look-through/overlap is unknown where unavailable. Correlation from actual prices is available.
- A failed new capture restarts from July 7 in a new attempt directory; no durable mid-run resume. Existing recordings are preserved. The $5 estimate threshold belongs to the completed capture campaign; this handoff does not authorise another paid run.
- The standalone portable launcher is replay-only. Live quiz works; new Live agent runs are refused. Normal configured Live startup is separate and unchanged.
- Saved reviews maintained the portfolio. That is a valid outcome, not a broken rebalance flow.

## Discussed, not implemented or newly authorised

**Benchmark chart:** the API already returns historical series; Mo can graph those without recapturing. Current comparisons are ours, buy-and-hold, quarterly rebalance, a global ETF and mechanical 5% rebalancing.

**S&P 500 comparison:** cached VUAG.LSE data already exists. A backend addition can calculate a GBP S&P 500 ETF proxy with matching dates, contributions, fees and costs. Label it as an ETF proxy; retain existing comparisons and the immutable recording. No Gemini calls are needed. Coordinate any API/type changes on the board.

**Higher-risk second scenario — STARTED (Dev authorised, 8 Nov, branch `dev/caroline-aggressive-profile`):** persona **Caroline** (`backend/app/config/demo_persona_caroline.yaml`) on a new **`aggressive`** profile: ~60% single stocks (floor 57%, cap 60%, ≤10% each), ~40% equity ETFs, no bonds, 2% cash. Priya and the four existing profiles are unchanged. Engine-only check on the real snapshot: 57.0% stocks (all 8) / 39.1% ETFs / 0% bonds. `runner --persona caroline` records her mandate. NOT done yet: a Caroline capture/recording (paid, needs Dev's go-ahead), demo/replay support for a second recording, and any UI to pick between personas. **Recording support (branch `dev/caroline-recording-support`):** `DEMO_PERSONA` setting (default priya) drives the mandate, `/api/profile/demo`, the refusal text and capture validation; `capture_demo.py --persona caroline`; `scripts/demo.py --persona caroline` loads `demo/caroline.manifest.json`; `scripts/make_demo_bundle.py` packages a READY capture into that bundle. Priya's bundle/recording are untouched. Caroline's real recording does not exist yet; it needs Dev's go-ahead for the paid capture and a distribution clearance statement for her bundle.
Original note: Dev asked whether it would be more engaging; it has not been run or authorised by this handoff. Preserve Priya as the main demo. Higher risk permits company stocks but does not guarantee selection or swaps. Current recorded-demo validation expects Priya's mandate; a separate scenario needs explicit support, not a silent persona/config replacement. Never force stock trades or tune frozen config to manufacture a story.

**Deployment:** not authorised. No deployment was performed. `DEPLOY_ENABLED` was absent at the last check; check current state rather than assuming that remains true.

## Dev's existing local session

The original capture/artifacts remain ignored under `backend/runs/demo/20261108T071746Z/`; teammates should use the portable bundle instead. Dev's existing app was left on Demo Home/Split view in VS Code at :5173, using a pinned sibling capture checkout. It is separate from the portable launcher. The detailed handover records PIDs; verify ownership before stopping anything. Do not disturb an unrelated service to claim the default port.
