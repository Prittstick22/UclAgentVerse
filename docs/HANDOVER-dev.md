# Handover for Dev's Claude Code session (from the planning chat, Sat 7 Nov 22:35)

Read `CLAUDE.md`/`AGENTS.md` first; everything below is already reflected in docs/issues. This file just lists the decisions and open items from the planning chat.

## Decisions already made
- Dev owns: Gemini agents **and** all paid/external APIs (accounts, payment, keys, adapters, `check_providers.py`), the finance kit (#60, #61), deck and pitch (#39, #69).
- Payments: EODHD "EOD Historical Data – All World" $19.99, one month (test the free plan first). DigitalOcean 2GB droplet only for the end-of-night deploy (~08:00), destroyed after judging (#56, #57). Gemini key is DeepMind-provided (internal billing).
- Deploy happens at the end (Jin, ~08:00); everything is developed locally until then.
- Data sharing: 4 announced switch moments (docs/13 "Data sharing"); `runs/year.sqlite` from the overnight batch is the single source of truth.
- Walk-forward: no component may see data after the sim day (`test_no_peeking`, #72). 2-week forecast is code-made from past data (#73); agent views become capped tilts (#74, feature).
- Finance kit = organisers' synthetic test data, reported separately from our real-data replay.
- Labels: do every `mvp` issue before any `feature`.

## Open items
- Confirm the meaning of "looks at its 2 weeks": (a) a 2-week horizon/cadence using all history up to today (what's implemented in docs/#73), or (b) only the last 2 weeks of data. Default: (a).
- Who runs the overnight batch on their laptop (03:00–07:00, awake + online)?
- Move issue #4's "hello-world deploy by 22:30" to the ~08:00 deploy plan.

## Dev's order
#27 Gemini ping → #3/#54/#55 provider keys + `check_providers.py` (send keys to Jin by ~23:00) → #60 finance kit → #28 → #29 → #30 → #31 → #37 overnight batch (02:30) → #61 → #32/#33/#34 → features → #39 deck, #69 rehearsal.
