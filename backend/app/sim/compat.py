"""Capture-resume compatibility switch. Owner: Dev.

`legacy = True` reproduces the behaviour from before the 8 Nov Caroline fixes (case_ evidence alias, stocks-floor
rounding margin, per-stock cap headroom), so a capture can replay an earlier attempt's saved Gemini answers exactly
(same prompts -> cache hits) up to the day the fixes take over. Default False = fixed behaviour everywhere
(Live, tests, simulations). Only app.sim.capture sets it.
"""
legacy: bool = False
