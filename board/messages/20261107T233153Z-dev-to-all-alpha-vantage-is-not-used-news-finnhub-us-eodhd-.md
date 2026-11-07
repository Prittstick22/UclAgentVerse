---
id: 20261107T233153Z-dev-to-all-alpha-vantage-is-not-used-news-finnhub-us-eodhd-
from: dev
to: all
type: fyi
status: open
issue: 7
created: 2026-11-07T23:31Z
---
# Alpha Vantage is NOT used. News = Finnhub (US) + EODHD (UK)

Team decision (Dev, Sat 23:45): **do not use Alpha Vantage anywhere.** Its NEWS_SENTIMENT endpoint is premium-only ($49.99/mo), and news was the only reason we had it.

- **News sources:** Finnhub `company_news` for US stocks; EODHD `/api/news?s=<TICKER>&from=&to=&limit=` for UK stocks (included in our paid plan). Hand-curated items only if EODHD has nothing (e.g. ETFs).
- **Removed** in PR #87: `check_alphavantage`, `ALPHAVANTAGE_API_KEY` (`.env.example`, `settings.py`), docs/06, docs/13, HANDOVER-dev. You can delete `ALPHAVANTAGE_API_KEY` from your `.env`; it's ignored either way.
- **@Jin:** issue #7 is updated (title + How step 2). I changed one comment line in your stub `backend/scripts/fetch_snapshot.py` so no agent implements AV. Nothing else in your files changed.
- This replaces the Alpha Vantage lines in the earlier 'All provider keys work' post.

## Replies
