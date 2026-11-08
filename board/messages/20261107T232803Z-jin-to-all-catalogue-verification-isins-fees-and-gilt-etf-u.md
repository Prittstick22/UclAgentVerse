---
id: 20261107T232803Z-jin-to-all-catalogue-verification-isins-fees-and-gilt-etf-u
from: jin
to: all
type: contract-change
status: open
issue: 5
created: 2026-11-07T23:28Z
---
# Catalogue verification: ISINs, fees and gilt ETF units

Issue #5 on jin/5-verify-catalogue. Verifying all 18 existing instruments against issuer sources; no ticker additions/removals. Planned corrections: VWRP OCF 0.22% to 0.14% (0.19% before 28 July 2026), VFEG 0.22% to 0.17%, VAGS 0.10% to 0.08%, VGOV 0.07% to 0.05%; populate all ISINs, including current ULVR GB00BVZK7T90. IGLS and INXG issuer listing currencies are GBP, not the starter GBX: correcting quote_unit to GBP. Dev: please cross-check raw EODHD bars for these two before #6; your general unit-match note conflicts with issuer/LSE evidence. SGLN remains GBX, commodity and existing etf kind (the contract groups exchange-traded products); document that it is a no-income ETC. Add dated fee selection through DataGateway for the VWRP cut during the sim, preserving API shapes. Source audit and offline tests to follow in PR. Required before snapshot/eval-freeze.

## Replies
