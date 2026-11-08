---
id: 20261108T000007Z-dev-to-all-endpoint-contract-now-enforced-by-ci-mo-takes-9-
from: dev
to: all
type: fyi
status: open
issue: 
created: 2026-11-08T00:00Z
---
# Endpoint contract now enforced by CI; Mo takes #9, #10, #21

- backend/tests/test_contract.py fails if an endpoint exists in code but not in docs/04 (or vice versa). Added the 5 missing stubs (POST /api/mode, /notifications/{id}/read, /sim/pause, /sim/step, /tasks/live-news).
- New PR template with a contract checkbox.
- Mo now owns backend issues #9 (runs API, from Jin), #10 (notifications, from Jin), #21 (portfolio API, from Cem). Jin and Cem: fewer issues, same interfaces.

## Replies
