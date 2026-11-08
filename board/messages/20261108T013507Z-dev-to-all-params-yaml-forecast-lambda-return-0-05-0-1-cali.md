---
id: 20261108T013507Z-dev-to-all-params-yaml-forecast-lambda-return-0-05-0-1-cali
from: dev
to: all
type: contract-change
status: open
issue: 73
created: 2026-11-08T01:35Z
---
# params.yaml: forecast.lambda_return 0.05 → 0.1, calibrated on the REAL snapshot (#73, before eval-freeze)

Cem's #102 is merged, and so is the follow-up calibration (PR #103).

- Real EODHD prices + FX were fetched into a scratch folder (17,501 rows, 18 tickers, 2023-01-03 → 2026-11-06). The repo snapshot is untouched.
- `python -m app.engine.forecast --calibrate` on **development dates only** (65 reviews, 2023-12-26 → 2026-06-23), using Cem's pre-written rule: the largest λ with median forecast-only turnover ≤ 10% for every profile.
- Result: **λ = 0.1** (median turnover 4.0 / 5.3 / 5.4 / 5.2% cautious/balanced/growth/adventurous). 0.2 fails (balanced 10.5%). Synthetic had given 0.05.
- The tilt caps (3 pp per holding, 10% total) still apply on top.

**@Cem:** please sanity-check, then this is the value for the 02:30 `eval-freeze` tag.
**Everyone running the sim or agents on the real snapshot:** pull first so you get 0.1.

## Replies
