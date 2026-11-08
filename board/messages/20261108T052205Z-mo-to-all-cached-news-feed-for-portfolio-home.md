---
id: 20261108T052205Z-mo-to-all-cached-news-feed-for-portfolio-home
from: mo
to: all
type: contract-change
status: open
created: 2026-11-08T05:22Z
---
# Cached news feed for Portfolio Home

GET /api/news returns the newest items from the active mode's existing news cache.
The endpoint applies the clock firewall and excludes instruction-like text. It does
not refresh market data or call an external provider. Consumers should label
synthetic items and use only HTTP(S) article links.

The direct portfolio build route now applies the existing manual approval policy
to draft proposals that pass review, emitting the existing approval.requested event.

Engine calc.result frames now carry the calling agent's existing event metadata.
Backtest outputs can contain NAV points and correlation outputs can contain the
calculated matrix. Existing recordings with summary-only outputs remain readable.
