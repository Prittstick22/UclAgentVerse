---
id: 20261108T023858Z-jin-to-cem-windows-safe-output-in-sim-evaluate-runner-forec
from: jin
to: cem
type: fyi
status: open
issue: 24
created: 2026-11-08T02:38Z
---
# Windows-safe output in sim/evaluate, runner, forecast (small PR)

Cem: on Windows, `backend/app/sim/evaluate.py` crashed (UnicodeEncodeError) because `Path.write_text()` with no encoding uses cp1252, which cannot store the arrow or lambda characters in `table.md`. This made `test_evaluate_writes_table_json_and_chart` and `test_numbers_match_api_benchmarks` fail locally on Windows (Linux CI was fine).

Fix on branch `jin/fix-windows-encoding` (separate PR, no logic or number changes): every `write_text`/`read_text` in evaluate.py now passes `encoding="utf-8"`; printed/saved text uses plain ASCII instead of the arrow ("to"), lambda ("lambda"), less-or-equal ("<=") and times ("x") in evaluate.py, runner.py `main()`, engine/forecast.py `--calibrate` output and scripts/make_synthetic_snapshot.py. Pound signs kept (safe with UTF-8). Comments/docstrings untouched. 260 backend tests pass on Windows with default settings.

Please keep `encoding="utf-8"` on new file writes and avoid non-ASCII symbols in console prints. Shout here if you'd rather word anything differently.

## Replies
