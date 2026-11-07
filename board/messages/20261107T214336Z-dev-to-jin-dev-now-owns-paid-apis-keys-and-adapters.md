---
id: 20261107T214336Z-dev-to-jin-dev-now-owns-paid-apis-keys-and-adapters
from: dev
to: jin
type: handoff
status: open
issue: 
created: 2026-11-07T21:43Z
---
# Dev now owns paid APIs, keys and adapters

Change of ownership (issues #3, #54–#57):
- Dev buys/verifies EODHD (#3; moved from you), signs up for Finnhub / Alpha Vantage / Alpaca, sets the EDGAR user agent (#54), and fixes/verifies the adapters in backend/app/data/adapters/ with scripts/check_providers.py (#55).
- You keep #5 (catalogue), #6/#7 (fetch_snapshot.py), the API, live mode and deploy. Build on the adapter signatures as they are; Dev will post a handoff with any gotchas (field names, GBX units, rate limits).
- Keys come to you privately (WhatsApp/password manager), never via git.
- Dev also sets up the DigitalOcean account + billing (#56) before your ~08:00 deploy, and cancels everything after judging (#57).

## Replies
