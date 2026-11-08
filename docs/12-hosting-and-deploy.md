# 12 · Hosting and deploy (DigitalOcean)

Owner: **Dev** (deploys). Jin owns the app-side pieces: #12, #78, #11.

## Shape

- **One DigitalOcean Droplet:** Ubuntu, Basic, **2 GB RAM** (pandas + CVXPY need it), London region (`lon1`). It's billed hourly: destroy it after judging.
- **Docker Compose with two services:**
  - **`app`:** our single image (repo-root `Dockerfile`). Stage 1 builds `frontend/`; stage 2 is Python with `backend/`. FastAPI serves `/api/*` and the built UI at `/`, on the same origin.
  - **`caddy`:** reverse proxy with automatic HTTPS (Let's Encrypt). It passes SSE through without buffering.
- **Persistent volume `./var` on the droplet:**
  - `state.sqlite` (events, ledger, memory, LLM cache)
  - `snapshot/` (data)
  - `runs/` (recorded overnight run)

  It survives redeploys.
- **Cron on the droplet** replaces a cloud scheduler for live mode:
  ```cron
  0 17 * * 1-5  curl -fsS -X POST -H "X-Task-Secret: $TASK_SECRET" https://$DOMAIN/api/tasks/live-eod
  30 21 * * 1-5 curl -fsS -X POST -H "X-Task-Secret: $TASK_SECRET" https://$DOMAIN/api/tasks/live-eod
  5 * * * *     curl -fsS -X POST -H "X-Task-Secret: $TASK_SECRET" https://$DOMAIN/api/tasks/live-news
  ```
  The cron daemon runs in UTC; London is on GMT in November, so these times line up.

## Costs

| Item | Cost |
|---|---|
| Droplet 2 GB | ~$12/month, billed hourly (check GitHub Student Pack credit) |
| EODHD EOD plan | $19.99, one month |
| Domain (optional) | Use a free DuckDNS subdomain or the IP |
| Gemini | DeepMind key, internal billing |

## First-time setup (Dev, ~20 min)

```bash
# On your laptop: create the droplet in the DO console (Ubuntu 24.04, Basic 2GB, lon1, add your SSH key)
ssh root@<ip>
curl -fsSL https://get.docker.com | sh
git clone https://github.com/Prittstick22/UclAgentVerse /opt/uclagentverse && cd /opt/uclagentverse
cp .env.example .env && nano .env      # keys, DOMAIN, DEMO_PASSCODE, TASK_SECRET, PUBLIC_DEMO=1
mkdir -p var/snapshot var/runs
docker compose up -d --build
docker compose logs -f app             # wait for "Uvicorn running"
curl -s https://$DOMAIN/api/health
```

Point the DNS A record (or DuckDNS) at the droplet IP **before** starting Caddy, so the HTTPS certificate is issued. Open ports 80/443 only (`ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw enable`).

## Deploys

- **Manual:** `ssh root@<ip> 'cd /opt/uclagentverse && git pull && docker compose up -d --build'`.
- **Automatic:** `.github/workflows/deploy.yml` does the same over SSH on every push to `main`, once these repo secrets are set: `DO_HOST`, `DO_USER`, `DO_SSH_KEY`. It's disabled until the secrets exist.
- **Copy data to the server:** `scp -r backend/data/snapshot/* root@<ip>:/opt/uclagentverse/var/snapshot/` and the same for `runs/year.sqlite`.

## The demo never waits on an API call (#78)

- **Demo:** reads only the recorded run (`runs/year.sqlite`) + the baked-in snapshot, with `LLM_MODE=replay`. It works with every external key removed.
- **Live mode:** the UI reads only cached data. Cron refreshes it in the background; no request handler calls a provider.
- **Live agent runs** (passcode) return a `run_id` instantly and stream over SSE.
- **Warm start:** everything is loaded at container start; one always-on container.

## Public link safety

- **`PUBLIC_DEMO=1`, `LLM_MODE=replay`:** visitors see a replay of the recorded year, at no Gemini cost.
- **Live investigations and chat** need the `X-Demo-Passcode` header (the UI asks once), with a per-IP rate limit and `DAILY_LLM_BUDGET_USD`.
- **How it works (#12, `backend/app/api/demo_guard.py`; all off unless `PUBLIC_DEMO=1`):**
  - `PUBLIC_DEMO=1` makes `LLM_MODE` default to `replay`. An explicit `LLM_MODE` in `.env` wins, so delete the `LLM_MODE=fake` line copied from `.env.example`.
  - `POST /api/chat` always needs the passcode. `POST /api/portfolio/build` and `POST /api/sim/start` with `run_agents: true` need it only while `LLM_MODE=live`; replays cost nothing and stay open. No `DEMO_PASSCODE` set = locked. Wrong or missing → 401 `unauthorized`.
  - Every `POST /api/*` except `/api/tasks/*` is limited to `RATE_LIMIT_PER_MINUTE` (default 30) per visitor IP, read from the last `X-Forwarded-For` entry Caddy adds → 429 `rate_limited`.
  - While `LLM_MODE=live`, once today's (UTC) recorded Gemini spend reaches `DAILY_LLM_BUDGET_USD`, new agent runs and chat get 429 `budget_exceeded` (`details: {limit, value}`) and a `budget.exceeded` event.
- **Secrets** live only in `/opt/uclagentverse/.env` on the droplet. Never in git or the frontend bundle.
- **Footer on every screen:** "Paper portfolio · Not financial advice".

## Cadence

| When | What |
|---|---|
| 03:00–04:15 | Deploy dry run: droplet up, current main at the real URL with HTTPS |
| 06:30 | Second deploy with the recorded runs |
| 08:00 | Final deploy; 08:30–09:00 smoke test (demo with no keys + live) |
| After that | Fixes only, each followed by a smoke test |
| **After judging** | Teardown (below) |

## Teardown after judging (Dev)

1. `scp root@<ip>:/opt/uclagentverse/var/{state.sqlite,runs/*} ./archive/` to keep the recorded runs.
2. In the DO console: **Destroy** the droplet, plus any snapshot or backup images, so hourly billing stops. Powering off still bills.
3. Remove the DNS record / DuckDNS entry.
4. Cancel the EODHD subscription. Rotate or revoke the API keys and the demo passcode.
