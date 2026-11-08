---
id: 20261108T0650Z-dev-to-all-evidence-inspection-fix
from: dev
to: all
type: contract-change
status: resolved
created: 2026-11-08T06:50:00Z
---
# Evidence inspection bug fix in progress

Dev authorised bug fixes across the app; Mo continues frontend design. Audited the current five-run recording: 33/39 distinct evidence refs resolve; catalogue, four case:*:v1 refs and proposal:* return 404 because run_views.find_evidence only handles news, filings and calculations.

Codex is adding backend resolvers with date/mode guards and immutable case-version storage. Evidence.kind gains case, proposal and earnings (plus existing catalogue/web handlers), with matching schemas/docs and an exported TS Evidence interface. No layout/CSS or event-shape changes. Existing EvidenceView renders title/excerpt/source without changes; old recordings stay read-only. Unknown/missing/future evidence must still return 404; never substitute another version or fabricate source text. Working branch dev/evidence-inspection-fix. No paid runs or deployment.

## Resolution

PR #137 merged (4a1d40d), both GitHub CI jobs green. All 435 backend tests and 7 frontend tests pass; build passes. All 39 current recorded UI evidence targets now return HTTP 200. Recording SHA unchanged. Backend restarted locally; frontend design files untouched. Exact case versions are now preserved. No paid model calls or deployment.
