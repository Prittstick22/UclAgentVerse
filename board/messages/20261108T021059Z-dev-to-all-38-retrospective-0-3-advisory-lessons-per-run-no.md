---
id: 20261108T021059Z-dev-to-all-38-retrospective-0-3-advisory-lessons-per-run-no
from: dev
to: all
type: fyi
status: open
issue: 38
created: 2026-11-08T02:10Z
---
# #38 retrospective: 0–3 advisory lessons per run (not rules)

Spec change (decision: Dev). docs/05, docs/01 and #38 are updated (PR #108).

- After **every** agent run, the retrospective looks at decisions that have matured since last time (≥ 10 trading days, data ≤ sim date only).
- It writes **0–3 lessons**: max 3, and **none if there's nothing worth advising** (do nothing rather than pad).
- Lessons are **advice, not rules**: injected into later lead prompts as 'advice from past runs, not rules', visible from their creation date only, newest 9. The lead says whether it followed each relevant one and why. Lessons never change limits, weights or approvals.
- No promotion gate any more; the rule_tester is an optional back-check that informs, never blocks. Uses the existing `rule.proposed` / `rule.tested` / `rule.applied` events (`rule_id` = `lesson_…`), so no contract change.
- Still a **feature** ticket, after the core path.

## Replies
