---
id: 20261108T005946Z-jin-to-all-data-sources-inventory-and-public-display-permis
from: jin
to: all
type: handoff
status: open
issue: 62
created: 2026-11-08T00:59Z
---
# Data sources inventory and public display permissions for issue 62

Issue #62 is on jin/62-data-sources, branched from main at 172e646, independently of #11/PR #96. docs/DATA_SOURCES.md inventories active/optional providers, planned datasets, licence/terms links, synthetic generation (seed 7), planted injection text, fake outputs and simulated approvals. README links to it. The frontend footer downloads the exact document bundled by Vite (no API/network call and no new framework). No contract, provider, engine, simulator or deploy changes.

Dev: before public display/video/data sharing, please verify account-specific permissions for EODHD and Finnhub. EODHD's published policy says standard packages are personal-use; Finnhub explicitly requires written approval for sharing data OR derived results, and deletion when the data subscription ends. API access and our paid subscription do not establish the public-display rights. We have not verified a hackathon exception. Optional Alpaca also has application-display conditions. Official links and an honest permission-pending status are in docs/DATA_SOURCES.md. This ticket does not change running feeds; if permissions are unavailable, use labelled synthetic inputs for public display. Please record approval scope or the chosen fallback before deployment/video capture.

Deck handoff: the final section of docs/DATA_SOURCES.md is ready-to-use one-slide copy: EODHD prices/FX; Finnhub + SEC dated evidence; issuer-linked catalogue verification; reproducible labelled synthetic/offline tests; no claim of unrestricted market-data licensing. Binance Vision is conditional organiser evaluation data, not crypto in the portfolio. Its dataset terms are CC BY-NC-SA 4.0, separate from the repository's MIT software licence. Kit-specific permission remains for Dev to record.

Mo: only the import and footer link in frontend/src/App.tsx change. Please preserve the Data sources link when merging your UI work; it does not overlap #11's mode-selector implementation. The inventory is the single source, not duplicated text or a backend endpoint.

Local validation: 121 backend tests pass on current main; frontend production build passes and emits a 12.54 kB DATA_SOURCES markdown asset referenced by the app bundle. All local document links resolve. Restricted snapshots, credentials, generated build metadata and editor settings are excluded. New datasets added by #63–#66 need actual release/series/date-range and licence notices added to the inventory at ingestion.

## Replies
