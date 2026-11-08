# Startup and verification

## Teammate / fresh clone

Install Python 3.11+ and Node.js 20+ with npm. From the repository root:

```bash
git pull
python scripts/demo.py --check
python scripts/demo.py --setup
```

Use `python3` if that is your Python command. Open http://127.0.0.1:8000/, choose Demo and open the timeline/Home. Subsequent starts need only `python scripts/demo.py`. Use `--port 8002` if 8000 is already occupied. Ctrl+C stops the server. See [demo instructions](../demo/README.md) for frontend hot reload with the recorded API.

## Check the result

Health must show historical mode, `as_of: 2026-11-06`, `llm_mode: replay`, `data_source: eodhd`. Home shows four assets. Inspect an asset graph, Connections/Matrix/Split view, timeline playback, benchmarks and evidence. A refresh must retain the recording. Real mode may test the quiz but this launcher's new Live investigations return a clear refusal; no provider calls are possible through the replay launcher.

The launcher verifies the archive and each extracted file every start. On a checksum error, preserve/rename the affected ignored cache directory and retry from an intact archive; do not edit the manifest to conceal a change. Git-tracked bundle bytes are the published source. Per-machine state belongs in `.demo-runtime/`, never in the bundle.

## Tests before publishing code

```powershell
# Windows, from repository root
$env:PYTHONIOENCODING='utf-8'
backend/.venv/Scripts/python -m pytest -q --tb=short backend/tests
cd frontend
npm test
npm run build
git restore tsconfig.tsbuildinfo
```

On macOS/Linux use `backend/.venv/bin/python`. Tests must not call providers. Restore generated `tsconfig.tsbuildinfo` only if your build changed it, preserving unrelated work.

Fetch/merge current main according to AGENTS.md, commit your work before merging, and inspect incoming frontend/shared-contract changes. Never edit `backend/app/config/*`, log keys, copy organiser files into code or deploy without Dev's instruction.

## New capture, only if Dev requests it

Use [capture instructions](../docs/demo-capture.md), a new campaign/attempt directory and its shared usage ledger. A candidate must pass complete-date/checkpoint, evidence, benchmark, no-fallback and replay-loader checks before READY. Do not overwrite the current bundle or the existing recording. Replacing a public bundle requires a new version, fresh hashes, appropriate source clearance and validation.
