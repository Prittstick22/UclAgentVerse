# Data sources, terms and synthetic-data disclosure

Owner: Jin. Account/permission owner: Dev. Reviewed 8 November 2026 for #62.
This inventory distinguishes implemented inputs from optional and planned
sources. A working API key establishes access, not permission to redistribute.
Provider terms and third-party rights are separate from this repository's code.
No account-specific public-display permission has been verified by this audit.

## Implemented and optional inputs

| Provider / status | What we use; date range | Terms / limits and attribution |
|---|---|---|
| EODHD — implemented | Catalogue daily OHLC/adjusted close and GBPUSD, requested 2023-01-02 to 2026-11-06; UK stock news from 2026-06-01; optional delayed quotes. Local price archive starts on 2023-01-03. | [Personal/commercial policy](https://eodhd.com/financial-apis/commercial-vs-personal-license-use): standard packages are personal-use; public/team use needs account-specific clarification from Dev. Do not treat the paid subscription as a redistribution licence. Cite EODHD, ticker, price date and raw unit. |
| Finnhub — implemented | US stock company news from 2026-06-01 to fetch end; historical earnings requested from 2023-01-01. Returned coverage is incomplete; see [text-fetch report](fetch-text.md). | [Terms](https://finnhub.io/terms-of-service): sharing data **or derived results** requires written approval; standard plans are personal-use unless expressly stated otherwise. Terms require deletion when the data subscription ends. Credit Finnhub and the originating article/publisher, preserve URL and publication time. Public-display permission is pending Dev's confirmation. |
| SEC EDGAR — implemented | US company submissions, 10-K/10-Q/8-K filing documents and selected passages, 2026-06-01 to fetch end. | [Access policy](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data): public downloads, declared contact User-Agent, maximum 10 requests/second. Public access is not a blanket copyright licence for every third-party exhibit. Preserve issuer, form, accession, URL and acceptance/availability timestamps; do not assume all filings are US-government-authored works. |
| Alpaca — optional adapter and provider checks | US IEX quotes and fallback price history; no Alpaca rows in the verified #6 EODHD snapshot. Exact range depends on a future configured fetch. | [Terms](https://files.alpaca.markets/disclosures/library/TermsAndConditions.pdf), [agreements](https://alpaca.markets/disclosures): personal/non-commercial service terms and separate exchange agreements apply; making an application available to others has additional notice/conditions. No blanket public feed or redistribution permission is assumed. |
| Vanguard and iShares/BlackRock — catalogue reference | Exact share classes, ISINs, trading units, income policy and OCF/TER; checked 2026-11-07. Dated VWRP fee history spans the simulation. | [Vanguard UK terms](https://www.vanguardinvestor.co.uk/terms-conditions), [iShares UK terms](https://www.ishares.com/uk/individual/en/compliance/terms-and-conditions). Link to issuer factsheets/pages rather than rehosting documents or logos. Field-level evidence is in [catalogue verification](catalogue-verification.md); no open licence for complete issuer documents is claimed. |
| Other catalogue evidence — reference only | Issuer investor-relations pages for Apple, Microsoft, NVIDIA, Amazon, AstraZeneca, Shell, Unilever and HSBC; LSE listing pages, FCA-hosted announcements, FDIC-hosted identifier evidence and justETF listing-unit cross-checks. | Exact source URLs appear in [the catalogue audit](catalogue-verification.md). These are factual identifier checks, not imported article/document datasets. Hosting by a regulator does not by itself establish rights to third-party text; no general reuse permission has been established. Preserve links and do not republish full source documents. |
| Binance Vision (via the organisers' finance kit) — evaluation only | Anonymised real hourly/4-hourly crypto price windows (2021 onward) downloaded **by the organisers' `bench.py` in memory** during the `real-markets` challenge (#61); nothing is stored in our repo except the kit's reports. | [Binance Vision dataset terms](https://data.binance.vision/), CC BY-NC-SA 4.0: non-commercial/educational use; attribute "Binance Vision"; no endorsement implied. Commercial use would need a separate Binance licence. |
| Google Gemini / Google Search grounding — service, not a price feed | Agent-generated findings; on-demand web context in **live mode only**. Fake mode uses canned outputs. Model knowledge is not dated market evidence. | [Gemini API terms](https://ai.google.dev/gemini-api/terms?authuser=00) and any hackathon/preview agreement governing the actual account. Grounding has attribution/display and use restrictions; Dev must verify the configured product's requirements. Retain source URLs. Generated summaries are not a licence to republish underlying publisher content or substitute for gateway prices. |
| AgentVerse finance kit — external evaluation only | Organiser synthetic `markets` cases; optional `real-markets` windows. No kit code or dataset is bundled with this app. Date range/run status must come from the actual evaluation report, not the app's replay dates. | See [kit provenance and evaluation protocol](finance-kit.md). The local organiser package's permission terms must be recorded by Dev; no public package licence is asserted here. Its real-market data rights are separate (next row). |
| Binance Vision — conditional evaluation source, not portfolio data | If Dev runs the kit's `real-markets` pack: real historical windows transformed/anonymised by the kit. Not a crypto allocation or live trading feed in this product. | [Dataset terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md): CC BY-NC-SA 4.0 except designated exceptions. Credit Binance Vision, identify rebasing/anonymisation/inversion, preserve the non-commercial/share-alike requirements for redistributed adaptations. The repository's MIT code licence is not the dataset licence. |

## Planned, not represented as loaded data

| Source / ticket | Intended role; range | Terms to record before ingestion |
|---|---|---|
| Bank of England / #64 | UK rates/macro; no series/range loaded by the current fetch script. | [Bank legal/database terms](https://www.bankofengland.co.uk/legal); database reuse has its own provisions and third-party exclusions. Record series IDs and applicable notice. |
| ONS / #64, #66 | CPI or household/investment statistics; edition/range not yet selected. | [ONS terms](https://www.ons.gov.uk/help/terms-conditions): most content under OGL, with exemptions. Attribute ONS, dataset, release date and licence; check third-party items. |
| FRED and ECB / #64 | Optional macro context; no series/range loaded. | [FRED terms](https://fred.stlouisfed.org/legal/) require attribution and checking each series' third-party rights. [ECB reuse policy](https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.en.html) applies to eligible ESCB statistics; verify the chosen series. |
| Companies House / #63 | Optional UK company filings; not yet fetched. | [Developer portal](https://developer.company-information.service.gov.uk/) and the selected product's licence/terms must be checked before use. Record filing origin and any third-party/personal-data exclusions; do not assume every submitted document has an open licence. |
| FCA Financial Lives / #66; FCA Handbook and legislation.gov.uk / #65 | Cited problem statistics and compliance references; no dataset imported here. | Start at the [official FCA survey](https://www.fca.org.uk/financial-lives); the exact selected report's copyright/permission notice remains to be checked (FCA legal pages were unavailable during this audit). [Official legislation reuse documentation](https://legislation.github.io/data-documentation/reuse-licence.html) describes OGL v3 and dual-licence exceptions. Record exact report/year, notice and attribution; these are not interchangeable licences. |
| World Bank Global Findex / #66 | Optional cited comparison statistics; release/indicator not yet selected. | [World Bank dataset terms](https://www.worldbank.org/ext/en/legal/terms-conditions/datasets): default CC BY 4.0 unless labelled otherwise, with additional terms. Check the selected release's metadata and acknowledge the World Bank, dataset and original source. |
| Yahoo Finance / yfinance — fallback only | Mentioned in the data plan, not used by the implemented snapshot fetcher. | Library availability is not a data licence. Verify [Yahoo terms](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html) and the market-data/publisher terms before any download or public display; no permission established here. |
| Alpha Vantage — not used | Old planning references only; no current adapter or snapshot dependency. | [Terms](https://www.alphavantage.co/terms_of_service/) cover personal/non-commercial use unless agreed otherwise. Do not imply the project sources news from Alpha Vantage. |

## Synthetic data and simulated actions

- **Development snapshot:** [make_synthetic_snapshot.py](../backend/scripts/make_synthetic_snapshot.py)
  uses NumPy's seeded generator (`--seed 7` by default), weekday dates from
  2023-01-02 through 2026-11-06 by default, and shared market/rate shocks plus
  asset-class drift and instrument-specific noise. Prices are exponentiated
  cumulative returns; GBPUSD follows a separate random path. OHLC values are
  identical within a bar and volume is zero. These are test paths, not measured
  returns, real liquidity or an exchange-holiday calendar.
- **Text and look-through fixtures:** synthetic outage/oil/injection articles,
  a synthetic NVIDIA filing passage and simplified VWRP constituent weights
  are authored test data, not issuer disclosures or historical holdings.
- **Injection demonstration:** `news_syn_inject` is intentionally planted
  instruction-like text. Even when included beside real news, it remains
  `source: synthetic`, `synthetic: true`, and visibly named a synthetic test item.
- **Where labelled:** snapshot manifest `label`, price/FX row `source`, news
  `source`/`synthetic`, filing `synthetic`, catalogue `data_source`, health
  `data_source`, and the app footer. The documentation/download link does not
  replace per-item labels. Any mixed cache must keep synthetic provenance;
  the live-cache work in #11 uses `synthetic+eodhd` for mixed seeded prices.
- **Fake agent outputs and mock UI:** `LLM_MODE=fake` produces deterministic
  canned responses; frontend mock fixtures are generated by
  [make_fixtures.py](../backend/scripts/make_fixtures.py). They are not live
  model reasoning. Label mock screens and do not present their numbers as an
  evaluation on real markets.
- **Paper money/actions:** profiles and amounts are fictional; ledger fills,
  costs and performance are simulated/backtested. Batch approval is a simulated
  policy response, not consent from a real customer. Label automated/batch
  approvals as such; no real account or real-money trade is connected.

## Publication and account-owner handoff

**Frozen demo bundle clearance (8 November 2026):** Dev, the provider-account owner, explicitly confirmed: "Public distribution: I confirm permission to redistribute the included EODHD/Finnhub data and article text." This records the account-owner confirmation for the completed July 7-November 6 demo bundle in `demo/manifest.json`. The bundled source files retain their actual timestamps and attribution; paper results and model-generated findings remain labelled. This confirmation applies to this frozen bundle, not automatically to future data acquisitions or other uses. No provider contract or secret is included.

Dev owns provider accounts, written permissions, deployment and teardown.
Before external display or dataset distribution, record permission covering
the intended audience, data fields, derived results, retention and screenshots.
This audit has **not** established a hackathon exception for EODHD/Finnhub or
Alpaca. If permissions are unavailable, use labelled synthetic data for the
public demo. This document does not change running feeds or deploy settings.

Keep uncleared raw snapshots, article text and all credentials out of public Git
history and public image layers until their use is cleared. Follow provider
retention/deletion terms when subscriptions end. Preserve factual source links
and the exact release/as-of dates with every displayed statistic. Attribution
does not itself grant redistribution rights.

Update this inventory whenever an adapter, manually downloaded dataset or
evaluation pack is added. Record the actual fetched range and source in the
snapshot manifest or run report; planned ranges are not proof of coverage.

## One-slide summary for Dev

**Traceable inputs, clearly separated from test data**

- Prices and GBPUSD: EODHD; dated company evidence: Finnhub and SEC EDGAR.
- Instrument identity/fees: issuer-linked catalogue audit; agents do not make
  up investment numbers. Optional services/evaluation sources are listed above.
- Offline development uses reproducible, seeded synthetic data. The injection
  item, fake model outputs and paper-trading results are explicitly distinguished.
- A source citation is not a distribution licence. Public display/retention
  permissions are an account-owner check; no unrestricted market-data licence
  is claimed. Link to this inventory from the deck's source notes.
