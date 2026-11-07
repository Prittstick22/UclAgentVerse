---
id: 20261107T235912Z-dev-to-jin-dev-is-taking-7-news-filings-earnings-fetch-addi
from: dev
to: jin
type: handoff
status: open
issue: 7
created: 2026-11-07T23:59Z
---
# Dev is taking #7 (news, filings, earnings fetch) + adding gw.earnings()

Hi Jin, Dev is taking **#7** off you (reassigned on GitHub). Please don't start it. If you already have work on it, reply here or on WhatsApp and we'll merge.

- **Where:** a new `backend/scripts/fetch_text.py` for the `news`, `filings` and `earnings` steps, plus a 3-line hook in `backend/scripts/fetch_snapshot.py`. Your #6 prices/FX code in that file won't be touched otherwise.
- **Output:** `news.jsonl`, `filings.jsonl` and `earnings.jsonl` in `backend/data/snapshot/`, same schemas as docs/06 §2.
- **Also, in #29:** I'm adding `DataGateway.earnings(tickers)` to `backend/app/data/gateway.py` (your file). It's about 10 lines mirroring `news()`, returns only rows with `date ≤ as_of` (strict firewall, no upcoming dates), and comes with a test. That's the only change to your file.
- **Order:** #29 first (now), then #7.

## Replies
