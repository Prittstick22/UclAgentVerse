# Paste-ready prompt

```text
You are taking over Dev's work on Prittstick22/UclAgentVerse, an AI paper-investment team for first-time UK investors.

Read AGENTS.md fully, then handoff/README.md, handoff/STATE.md and handoff/RUNBOOK.md. Read the newest "Resume here" entry in docs/HANDOVER-dev.md; older entries are history, not new run authorisation.

Pull main safely and check the board for dev/all with PYTHONIOENCODING=utf-8. Preserve existing work and recordings. The complete real-data Priya balanced demo is bundled in demo/ with relative paths and SHA256 verification. Run `python scripts/demo.py --check`; for first local startup run `python scripts/demo.py --setup`. This works on Windows/macOS/Linux with Python 3.11+ and Node 20+. No .env/API keys are needed. Choose Demo at http://127.0.0.1:8000/; use --port 8002 if that port is occupied. Dev wants app pages inside VS Code's integrated browser on his machine.

The demo is complete July 7-November 6, 2026: 89 days, 9 agent runs, 48 actual Argon/Flash calls, estimated $0.4335445. All 8 reviews maintained; 4 ETF holdings. All 54 evidence refs and no-provider replay were verified. Historical playback never calls providers or changes the saved SQLite. The portable launcher disables new Live investigations; its Live quiz is separate. Normal configured Live operation is a different startup.

The current task was portability and handoff. Do not infer authorisation to start another paid capture, change the persona, force trades, change frozen config or deploy. Dev will return with the next instruction. Candidate next work discussed: a chart of existing benchmark series, plus an S&P 500 ETF-proxy comparison derived deterministically from cached VUAG.LSE with matching GBP dates/contributions/costs. This needs no Gemini rerun. A higher-risk second scenario was only discussed; preserve Priya and wait for explicit scope before doing it.

Mo is improving frontend design. Coordinate narrowly, keep recorded data immutable, and post contract changes before changing shared API/type/event shapes. Never print keys or .env contents. Never include Live state/logs in the public bundle. Dev confirmed public distribution permission for the currently included EODHD/Finnhub data and article text; that confirmation is recorded in docs/DATA_SOURCES.md and demo/manifest.json and does not automatically cover future acquisitions.

Use backend/.venv/Scripts/python on Windows or backend/.venv/bin/python elsewhere. Tests must be offline. Before a PR run the full backend suite and frontend tests/build; restore generated tsbuildinfo if changed. Keep organiser kit files out of the repo. Before stopping, update and push the current handover and report exactly what passed, what is merged and what remains.
```
