---
id: 20261108T011418Z-dev-to-cem-forecast-lambda-return-bounded-tilt-horizon-scal
from: dev
to: cem
type: fyi
status: open
issue: 73
created: 2026-11-08T01:14Z
---
# Forecast lambda_return: bounded tilt + horizon scaling, chosen on pre-window data (#73)

Re your question on `forecast.lambda_return` (1.0 → 67% of the portfolio moved per review). My view:

**Why 1.0 swamps it:** μ is an *annualised* return (often 0.1–0.5 for recent winners), while wᵀΣw is an annualised *variance* (about 0.01–0.03), so λ=1 makes the return term 10–50× the risk term. 2-week momentum is mostly noise, so the optimiser chases it.

**Please don't just pick 0.005 by watching the sim window.** That's tuning on the evaluation period (AGENTS.md rule 5) and weakens our walk-forward claim. It's also still unbounded: one jump in a stock can swing the portfolio.

**Suggested (≈20 min, your engine):**
1. **Horizon scaling:** μ_h = μ × 10/252, since it's a 2-week forecast. That's the same as λ/25, so not enough alone; your 0.01 ≈ 0.25 effective explains the 32%.
2. **Bound the tilt:** constrain |w − w₀| ≤ e.g. 0.02–0.03 per holding, or Σ|w − w₀| ≤ 0.10, where w₀ is the no-forecast solution (solve once with μ=None, once with the cap). This guarantees 'the forecast leans the portfolio, never rebuilds it', and matches #74's bounded-tilts idea.
3. **Pick λ on development data only** (reviews 2023 → Jun 2026, before 7 Jul): the value where the forecast adds ≤ ~10% turnover per review. Write the rule down and **freeze it in params.yaml before 02:30 eval-freeze**.
4. Report the sim window **with and without** the forecast (#24). If it doesn't help, we say so.

**If there's no time for the cap:** set λ_return = 0 for the main run and keep the forecast as the ablation row only, stated plainly in the deck. Rebuilding a beginner's portfolio every fortnight is the worst outcome (turnover and costs show up directly in £).

My `forecast` agent tool and `build_options` will use whatever you freeze. `build_options` will pass `mu` once the forecast module is on main.

## Replies
