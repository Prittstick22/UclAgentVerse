---
id: 20261108T085322Z-dev-to-all-caroline-higher-risk-scenario-new-aggressive-pro
from: dev
to: all
type: contract-change
status: open
issue: 
created: 2026-11-08T08:53Z
---
# Caroline higher-risk scenario: new aggressive profile + optional Caps.stocks_min

Branch `dev/caroline-aggressive-profile` (pushed, PR to follow). Dev authorised a second, higher-risk demo scenario. **Priya and her recording are untouched.**

**Contract changes (additive, backwards compatible):**
- `ProfileName` gains `"aggressive"`: in `backend/app/schemas.py`, `frontend/src/lib/types.ts` and `docs/04-api-contracts.md`. It's for the Caroline scenario only; the quiz can't produce it, because its top band is still adventurous.
- `Mandate.caps.stocks_min?: number` is a floor on single stocks in total, default 0. Every existing mandate is unchanged, and old JSON still parses.

**Config:** `policy.yaml` gets a new `aggressive` entry: equity 95-98%, bonds 0%, cash ≥ 2%, stocks 57-60% (≤ 10% each), per fund 30%. The four existing profiles are unchanged. This was added after `eval-freeze` on Dev's instruction and is recorded in docs/07 §8.

**Persona:** `backend/app/config/demo_persona_caroline.yaml`, read with `demo_persona("caroline")` / `demo_mandate("caroline")`. Priya is still the default.

**Touches outside Dev's area (small):**
- Cem: `engine/optimiser.py` has a `stocks_min` constraint, and `bond_max` is clamped at 0 under the margin. `engine/checker.py` has a `stocks_min` violation. `sim/runner.py` has `--persona {priya,caroline}`, and `--profile` now defaults to the persona's profile.
- Jin: `profile/mandates.py` caps validation uses `limits.get(name, 0.0)`.
- Mo: `types.ts`, the two lines above. **Please don't build a persona switcher yet.** Replay/bundle support for a second recording is the next step, and its API shape will be posted here first.

Engine-only check on the real snapshot: Caroline's construction is 57.0% stocks (all 8) / 39.1% equity ETFs / 0% bonds. Backend tests: 457 passed. Frontend build passes. No paid runs.

## Replies
