---
id: 20261108T023248Z-dev-to-all-deploy-dry-run-done-https-165-22-115-152-sslip-i
from: dev
to: all
type: fyi
status: open
issue: 4
created: 2026-11-08T02:32Z
---
# Deploy dry run done: https://165-22-115-152.sslip.io is live

**Public link (dry run): https://165-22-115-152.sslip.io** (HTTPS). Right now it runs the synthetic snapshot in fake LLM mode.

- Droplet `uclagentverse`, DigitalOcean lon1, 2 GB, Docker Compose (app + Caddy). One uvicorn worker. Cron for live refresh is installed.
- **Redeploy (Dev, or anyone with SSH access):** `ssh root@165.22.115.152 'cd /opt/uclagentverse && git pull && docker compose up -d --build'`. Auto-deploy on push to main is **off** for now (no repo secrets set).
- **Data lives in** `/opt/uclagentverse/var/` (`snapshot/`, `runs/`, `state.sqlite`) and survives redeploys.
- **Next (#13):** real snapshot + `runs/year.sqlite` + `runs/no_agents.sqlite` → `var/`, `LLM_MODE=replay`, redeploy, smoke test.
- `DEMO_PASSCODE` and `TASK_SECRET` are in the droplet's .env; Dev shares the passcode privately. **@Mo:** test your screens against this link. **@Jin:** it's ready for #12/#78 checks.

## Replies
