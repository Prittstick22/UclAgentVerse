# Run the recorded demo on your machine

Every clone includes the compressed, verified Priya recording and its market snapshot. No data download, API key, `.env`, paid model call or new portfolio construction is needed for replay.

Prerequisites: **Python 3.11+ and Node.js 20+ with npm**. Use `python3` instead of `python` where required on macOS/Linux. First setup needs internet access for software dependencies; subsequent replay works offline.

From the repository root:

```bash
git pull
python scripts/demo.py --setup
```

Open **http://127.0.0.1:8000/** and choose **Demo → Open demo timeline → Home**. In Dev's workspace, use VS Code's integrated browser. Other teammates can use their normal browser.

Later starts:

```bash
python scripts/demo.py
```

If port 8000 is occupied, use `python scripts/demo.py --port 8002` and open the printed URL. The launcher does not stop another service. Ctrl+C stops this demo server.

Verify the bundle without installing dependencies or starting a server:

```bash
python scripts/demo.py --check
```

The archive is checked against `manifest.json`, extracted into ignored `.demo-data/`, and each extracted file is checked again. Existing changed files are refused rather than silently overwritten. The original recording is loaded read-only into memory. Per-machine questionnaire state goes under ignored `.demo-runtime/`; it is never shared.

## Caroline (higher-risk scenario)

A second, separate recording follows **Caroline** (aggressive profile: about 60% single stocks, 40% equity ETFs, no bonds) over the same window. It is a different run, with its own captured requests and responses, and it never replaces Priya's. Its bundle is `demo/caroline.manifest.json` plus `demo/assets/caroline-*.zip`, added when the capture has been validated and packaged (see below). Until then `--persona caroline` stops with a "No such file" error.

```bash
python scripts/demo.py --persona caroline     # same setup, same port options; Priya remains the default
python scripts/demo.py --persona caroline --check
```

One server replays one persona (`DEMO_PERSONA`, set by the launcher). Nothing in the frontend or API shapes changes: `/api/profile/demo` returns whoever the server is replaying.

**Adding Caroline's recording** (Dev, after the paid capture; see [capture workflow](../docs/demo-capture.md)):

```bash
python scripts/make_demo_bundle.py --persona caroline --attempt <attempt dir with READY.json>     --snapshot <the capture's inputs dir> --clearance "<your exact distribution-permission wording>"
python scripts/demo.py --persona caroline --check
git add demo && git commit && git push
```

The builder refuses an attempt without `READY.json`, files that look like they contain a credential or request URL, a missing clearance statement, and overwriting an existing bundle. Priya's clearance does not automatically cover any newly fetched data, so state the permission for what Caroline's bundle contains.

## Frontend development against the recording

Keep the backend on port 8000 for Vite's existing proxy:

```bash
python scripts/demo.py --setup --api-only
```

In another terminal, from `frontend/`:

```powershell
# Windows PowerShell
$env:VITE_MOCK='0'; npm run dev
```

```bash
# macOS/Linux
VITE_MOCK=0 npm run dev
```

Install frontend dependencies with `npm ci` first if needed. Open the Vite URL, usually http://127.0.0.1:5173/. `VITE_MOCK=0` is required; default development mock mode uses fixtures instead of this recording. For the single-server built UI, rebuild with `VITE_MOCK=0` after frontend changes, or rerun `--setup`.

## What is included

- July 7–November 6, 2026: 89 trading days; initial construction plus eight maintain reviews.
- Real captured Argon/Flash outputs, events, cases, proposals, fills, performance and four benchmark strategies plus the agent portfolio.
- EODHD prices/FX, real Finnhub/EODHD news, SEC filings and cached earnings. Original source dates and labels are retained.
- Four holdings; all 54 evidence links verified. Synthetic market fixtures are excluded. Missing ETF constituents are **unknown**, not zero; price graphs and the correlation lattice still work.

Paper trading and historical simulated results only; not a forecast or financial advice. Priya is fictional. Dev confirmed public distribution of the included EODHD/Finnhub data and article text on November 8, 2026; the confirmation and source attribution are recorded in the manifest and [data-source inventory](../docs/DATA_SOURCES.md).

## Live mode

This launcher forces replay and clears provider credentials in its child process without editing `.env`. Live questionnaire testing is available, but **new Live investigations are explicitly disabled**. Configured Live operation uses the normal project startup, its own credentials and separate state. The portable launcher never consumes model credits.

The bundle is versioned and immutable. Do not overwrite it with a new capture. See [capture workflow](../docs/demo-capture.md) and [agent handoff](../handoff/README.md).
