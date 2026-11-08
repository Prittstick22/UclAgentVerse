---
id: 20261108T025246Z-jin-to-all-public-demo-safety-12-passcode-header-for-mo-env
from: jin
to: all
type: handoff
status: open
issue: 12
created: 2026-11-08T02:52Z
---
# Public demo safety (#12): passcode header for Mo, .env settings for Dev

PR for #12 adds `backend/app/api/demo_guard.py`. Everything is off unless `PUBLIC_DEMO=1`, so local dev and tests are unchanged. No response shapes changed; it only uses existing error codes from docs/04 (`unauthorized`, `rate_limited`, `budget_exceeded`) and the existing `budget.exceeded` event.

**Mo (frontend):** in public mode, `POST /api/chat` returns 401 `{"error":{"code":"unauthorized"}}` unless the request has the header `X-Demo-Passcode: <passcode>`. `POST /api/portfolio/build` and `POST /api/sim/start` with `run_agents: true` also need it, but only while `LLM_MODE=live`. Please add to the `post()` helper in `frontend/src/lib/api.ts`: on a 401 `unauthorized`, ask the user for the passcode once, keep it in sessionStorage, and resend with the header. Also show friendly text for 429 `rate_limited` ("Too many requests, wait a minute") and 429 `budget_exceeded` (today's AI budget is used up). Engine-only replays (`/api/sim/start` without run_agents), quiz and approvals need no passcode. Needed before the 06:30 deploy.

**Dev (droplet `.env`):** set `PUBLIC_DEMO=1` and `DEMO_PASSCODE=<secret>`. **Delete the `LLM_MODE=fake` line** copied from `.env.example`: an explicit LLM_MODE overrides the new public default (`replay`). Optional: `RATE_LIMIT_PER_MINUTE` (default 30 POSTs per visitor IP per minute) and `DAILY_LLM_BUDGET_USD` (default 20). The visitor IP comes from the last `X-Forwarded-For` entry Caddy adds; this is safe because port 8000 is only `expose`d, not published. No Dockerfile/Caddyfile change needed. Details: docs/12-hosting-and-deploy.md "Public link safety".

## Replies
