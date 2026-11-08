---
id: 20261108055335Z-dev-to-mo-smoke-onboarding-help-text
from: dev
to: mo
type: fyi
status: open
issue: 41
created: 2026-11-08
---
# Historical smoke passed; onboarding fields need help text

User tested onboarding and asked what Review every and Exclusions mean. Please clarify frontend/src/screens/Quiz.tsx when convenient: Review every is trading days (10 approximately fortnightly); exclusions currently match exact tickers or catalogue sleeves, not natural-language sectors. Blank means no exclusions. Do not imply a review automatically trades. No frontend files changed by Codex.

The 62px onboarding bug was resolved after pulling your merged #133: verified 640px centred quiz at 1920px viewport; 7 frontend tests pass. One real historical July 7 build passed all 7 gates (Argon lead, Flash specialists, 80.49s, estimated $0.1243); proposed holdings have purposes/evidence, batch approved, next-close orders queued. No further days advanced.

Observed UI limitations, accepted for this smoke: historical mode hides approval actions even for editable capture; Play controls are still visible on Timeline in public Live; historical in-progress agent runs are treated as archived replay rather than live streaming. Future desired UX: Play only for saved Demo, and public Live is today's date. Keep these separate from the completed smoke result.

No new framework or contract change requested by this note.

## Replies
