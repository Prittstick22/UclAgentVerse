# Local demo capture

Capture runs use a fresh Priya simulation, real cached input evidence and the frozen configuration. They do not deploy.

Prepare a new campaign directory outside tracked files with validated EODHD prices/FX and real text evidence in an inputs subdirectory. Remove synthetic records only from that copy, including the planted injection item and synthetic ETF constituent list. Preserve original source timestamps and a separate exclusion/hash audit.

From backend, use the existing virtual-environment Python:

```powershell
python scripts/capture_demo.py --snapshot <campaign>/inputs --out <campaign>/preflight --budget-file <campaign>/budget.json --budget-usd 5 --engine-only
python scripts/capture_demo.py --snapshot <campaign>/inputs --out <campaign>/attempts/001 --budget-file <campaign>/budget.json --budget-usd 5 --env-file <original-repo>/.env
```

Use backend/.venv/Scripts/python on Windows. The optional env-file supplies local credentials without copying or printing them. Every output directory must be new; no existing recording is replaced. Agent mode selects Argon for deep roles and Flash for fast roles, July 7 through November 6, with the existing batch approval policy. Engine preflight uses no models.

The shared budget ledger accounts for returned provider usage, including invalid schema responses, across attempts. It checks before every new provider attempt. Already-running parallel requests can take the estimate above the threshold. Estimated usage cannot establish charges for provider failures that return no usage.

A failed or cancelled attempt retains its database and attempt.json, without READY.json. Retry from July 7 in a new directory after diagnosis, using the same budget ledger. No durable simulation resume or automatic cache transfer is implemented. A stale budget.lock after an abruptly killed process requires checking that no capture is running before removing that exact lock.

Only a complete, validated agent capture gets READY.json: complete dated ticks/checkpoints, initial mandate, invested portfolio, four benchmark strategies plus ours, inspectable evidence, no technical agent failure or engine construction fallback, unchanged inputs and a successful read-only replay load. The recording and inputs remain versioned; activate their paths only after validation. Keep the previous working recording.

Missing ETF constituent data is unknown, never zero. Supplied partial constituents provide a lower bound. The final real-only capture deliberately has no invented look-through holdings.
