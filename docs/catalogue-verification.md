# Instrument catalogue verification (#5)

Checked 7 November 2026. All 18 existing tickers retained: nine UCITS ETFs,
one physical-gold ETC and eight ordinary/common stocks. Provider suffixes
`.LSE` and `.US` are EODHD identifiers, not issuer exchange symbols.

`currency` is the trading/valuation currency, not the fund base currency or
the nominal denomination of a share. `quote_unit` describes the raw price:
GBP means pounds, GBX means pence. Never divide a GBP bar by 100.
The issuer listing tables and LSE identify IGLS and INXG as GBP, correcting
the starter's GBX values. Dev's [provider handoff](../board/messages/20261107T232248Z-dev-to-all-all-provider-keys-work-gemini-eodhd-paid-finnhub.md)
reports coverage for all tickers, but its general unit-match statement needs
these two corrections checked against raw provider bars when fetching #6.

OCF/TER below is percent per year; JSON stores fractions (0.14% = 0.0014).
Stocks have no fund OCF: zero does not mean trading is cost-free.

| Ticker | ISIN | Listing / raw unit | Income | OCF/TER | Evidence |
|---|---|---|---|---|---|
| VWRP.LSE | IE00BK5BQT80 | London / GBP | Accumulating | 0.14% | [Vanguard](https://www.vanguard.co.uk/uk-fund-directory/product/etf/equity/9679/ftse-all-world-ucits-etf-usd-accumulating) |
| VUAG.LSE | IE00BFMXXD54 | London / GBP | Accumulating | 0.07% | [Vanguard factsheet](https://fund-docs.vanguard.com/SandP_500_UCITS_ETF_USD_Accumulating_9694_EU_INT_UK_EN.pdf) |
| VUKG.LSE | IE00BFMXYP42 | London / GBP | Accumulating | 0.09% | [Vanguard](https://www.vanguard.co.uk/uk-fund-directory/product/etf/equity/9580/ftse-100-ucits-etf-gbp-accumulating) |
| VERG.LSE | IE00BK5BQY34 | London / GBP | Accumulating | 0.10% | [Vanguard](https://www.vanguard.co.uk/professional/product/etf/equity/9682/vanguard-ftse-developed-europe-ex-uk-ucits-etf-eur-accumulating) |
| VFEG.LSE | IE00BK5BR733 | London / GBP | Accumulating | 0.17% | [Vanguard](https://www.vanguard.co.uk/uk-fund-directory/product/etf/equity/9678/ftse-emerging-markets-ucits) |
| VAGS.LSE | IE00BG47K971 | London / GBP | GBP-hedged, accumulating | 0.08% | [Vanguard](https://www.vanguard.co.uk/uk-fund-directory/product/etf/bond/9685/global-aggregate-bond-ucits-etf-gbp-hedged-accumulating) |
| VGOV.LSE | IE00B42WWV65 | London / GBP | Distributing | 0.05% | [Vanguard](https://www.vanguard.co.uk/uk-fund-directory/product/etf/bond/9501/uk-gilt-ucits-etf-gbp-distributing) |
| IGLS.LSE | IE00B4WXJK79 | London / GBP | Distributing | 0.07% | [iShares listing table](https://www.ishares.com/uk/professionals/en/products/251804/igls) |
| INXG.LSE | IE00B1FZSD53 | London / GBP | Distributing | 0.10% | [iShares](https://www.ishares.com/uk/individual/en/products/251717/ishares-indexlinked-gilts-ucits-etf?switchLocale=y), [LSE](https://www.londonstockexchange.com/en/quote/etps/INXG/ishares-ii-plc) |
| SGLN.LSE | IE00B4ND3602 | London / GBX | No income | 0.12% | [iShares](https://www.ishares.com/uk/individual/en/products/258441/ishares-physical-gold-etc?siteEntryPassthrough=true&switchLocale=y), [listing units](https://www.justetf.com/uk/etf-profile.html?isin=IE00B4ND3602) |
| AAPL.US | US0378331005 | Nasdaq / USD | Common stock | 0 | [Apple](https://investor.apple.com/faq/default.aspx), [common-stock CUSIP filing](https://www.sec.gov/Archives/edgar/data/320193/000110465921017199/tv0010-appleinc.htm) |
| MSFT.US | US5949181045 | Nasdaq / USD | Common stock | 0 | [Microsoft ticker and CUSIP](https://www.microsoft.com/en-us/Investor/faq) |
| NVDA.US | US67066G1040 | Nasdaq / USD | Common stock | 0 | [NVIDIA ticker and CUSIP](https://investor.nvidia.com/investor-resources/faqs/) |
| AMZN.US | US0231351067 | Nasdaq / USD | Common stock | 0 | [Amazon](https://ir.aboutamazon.com/faqs/default.aspx), [CUSIP Global Services letter, FDIC-hosted](https://www.fdic.gov/media/171376) |
| AZN.LSE | GB0009895292 | London / GBX | Ordinary shares | 0 | [AstraZeneca](https://www.astrazeneca.com/investor-relations/faqs.html) |
| SHEL.LSE | GB00BP6MXD84 | London / GBX | Ordinary shares | 0 | [Shell identifiers](https://shell.gcs-web.com/news-releases/news-release-details/shell-sets-out-expected-timetable-simplification) |
| ULVR.LSE | GB00BVZK7T90 | London / GBX | Ordinary shares | 0 | [Unilever issuer filing](https://www.sec.gov/Archives/edgar/data/217410/000165495426000947/a9450r.htm), [issuer announcement, FCA-hosted](https://data.fca.org.uk/artefacts/NSM/RNS/8cc23b1b-7575-42d1-af1d-da42d8b60422.html) |
| HSBA.LSE | GB0005405286 | London / GBX | Ordinary shares | 0 | [HSBC](https://www.hsbc.com/investors/shareholder-and-dividend-information/investor-faqs) |

US ISINs use the issuer/common-stock CUSIP prefixed with US and the ISIN
check digit; tests validate the complete identifier checksum. UK stocks are
the London ordinary shares, not their US depositary receipts. ULVR uses the
post-consolidation ISIN, not obsolete GB00B10RZP78. Historical adjusted prices
before the consolidation must retain the provider's corporate-action adjustments.

## Fee dates and historical mode

[Vanguard's change notices](https://www.vanguardinvestor.co.uk/investment-information/fund-changes)
confirm VAGS 0.10% to 0.08% and VGOV 0.07% to 0.05% on 1 July 2025;
VFEG 0.22% to 0.17% on 7 October 2025. These precede our simulation.
VWRP fell from 0.22% to 0.19% on 7 October 2025, then to 0.14% on
28 July 2026 (announced 21 July). Its internal `ocf_history` lets
`DataGateway.catalogue()` select by the simulation clock, so the 7 July
start sees 0.19%, not the future fee. The API still returns one numeric `ocf`.
The other verified fields are reference metadata for the supported
7 July–6 November 2026 simulation, not a complete historical security master.

## ETC convention

SGLN is a physically backed, non-UCITS ETC with no income; it is not an
accumulating UCITS fund. Keep its existing `kind: etf` transport grouping
(the current contract only supports etf/stock), `asset_class: commodity`,
explicit ETC name and `accumulating: false`. False means not accumulating;
it does not imply that this instrument distributes dividends.

This audit records factual reference metadata and source links, not a
redistribution licence for issuer documents or market data. Provider/data
licence inventory remains tracked in #62.
