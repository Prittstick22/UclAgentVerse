# Finance project test report

**CHALLENGE (self-serve): hidden real-markets cases**

Dataset: 60 cases; seed: None; source: Price returns derived from Binance Vision public data (CC BY-NC-SA 4.0). Not endorsed by Binance. Months drawn: 58 (hidden until reveal)..

Exact checks: **0 passed, 0 failed, 0 execution errors**.
Market simulations completed: **60**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `f75306ad03765956d51bc558656a8abd2e211fd061070cb2f8d8cc87a005d9a1`
- Seed: fresh random; revealed in SEED-REVEAL.txt after this run
- Kit fingerprint: `5c90bf815848f4edd85bb2446e00382a24f003d936b3bad72f297a3b7885dad9` (compare with the organisers' published value)
- Project commit: `f9863279ad78922ad350b516480971f2eb35d5e3`, uncommitted changes: 2
- Provenance review: none flagged.

## Coverage

| Task / scenario family | Pass | Fail | Error | Simulated |
| --- | ---: | ---: | ---: | ---: |
| markets / real_anonymised | 0 | 0 | 0 | 60 |

## Strategy results after costs

| Case | Final cash | Profit / loss | Buy-and-hold final | Cash baseline | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1f458bf61d0dceedbcb7 | £10,079.27 | £1,007.93 | £10,618.38 | £9,071.34 | 14.38% |
| 11ac917d73913911c874 | £8,794.66 | -£471.83 | £8,743.64 | £9,266.49 | 8.31% |
| 87e400fd342103668466 | £1,432.96 | -£280.78 | £1,427.50 | £1,713.74 | 20.78% |
| 0504f0917a7cf25e2c4f | £5,177.99 | -£1,089.89 | £5,263.22 | £6,267.88 | 23.90% |
| 3e9027a9de4da03f39c2 | £2,835.06 | -£641.10 | £3,069.94 | £3,476.16 | 18.44% |
| eb5698e3f694a0de4553 | £8,280.89 | £178.11 | £8,551.66 | £8,102.78 | 16.76% |
| 9452fe6be5295e1cf9ee | £2,714.54 | -£134.72 | £2,714.54 | £2,849.26 | 9.58% |
| 4069c3aa678da2ff2dc5 | £2,744.44 | £292.93 | £2,744.44 | £2,451.51 | 3.73% |
| fdfa40f4b754b5a21b89 | £3,378.79 | £33.36 | £3,378.79 | £3,345.43 | 4.38% |
| f9ffb67d6acc1b0cf2a0 | £2,023.15 | £5.80 | £2,023.15 | £2,017.35 | 5.36% |
| aeea7d21fa3babd0ae63 | £1,354.57 | -£74.81 | £1,354.57 | £1,429.38 | 10.78% |
| bde507708c2b9030deaf | £11,835.92 | £2,492.91 | £11,575.13 | £9,343.01 | 16.88% |
| b0e9743c2c4e5d31541f | £3,455.47 | -£685.68 | £3,128.97 | £4,141.15 | 21.05% |
| 382b448496044e67ad98 | £5,053.32 | £1,404.71 | £4,418.20 | £3,648.61 | 15.41% |
| e671876ac470a146f414 | £6,083.19 | £485.84 | £6,083.19 | £5,597.35 | 7.19% |
| 8adab33f426c80463b9d | £9,746.59 | £161.86 | £9,746.59 | £9,584.73 | 1.20% |
| 08de921b9c012f468975 | £9,905.32 | £207.32 | £9,850.36 | £9,698.00 | 1.80% |
| 4f44c2896384f61f3b7d | £5,034.00 | £261.55 | £4,992.85 | £4,772.45 | 7.75% |
| d23112cc3f5af1018403 | £4,258.51 | -£243.54 | £4,258.51 | £4,502.05 | 9.87% |
| 621d501b3c46bf65af17 | £9,745.19 | -£36.04 | £9,745.19 | £9,781.23 | 3.44% |
| d9d68f81ff38bb457b9c | £5,928.06 | -£308.72 | £5,928.06 | £6,236.78 | 9.04% |
| 3b94613078eec289039e | £6,549.23 | £32.33 | £6,658.95 | £6,516.90 | 4.92% |
| ad38ec3df672c6ee1254 | £7,628.49 | -£874.33 | £7,593.04 | £8,502.82 | 16.98% |
| e4d3ac65e647ffc75be8 | £12,838.50 | £2,978.36 | £14,737.82 | £9,860.14 | 22.03% |
| 09dc377bb8bad292018f | £1,494.35 | £115.55 | £1,465.81 | £1,378.80 | 2.34% |
| d13fe75ce76497da0a07 | £1,455.89 | -£285.50 | £1,540.07 | £1,741.39 | 19.52% |
| 09096403912ecac912e5 | £7,412.24 | -£1,143.06 | £2,741.83 | £8,555.30 | 16.92% |
| 7183def150921c248f4d | £3,167.68 | £765.06 | £3,167.68 | £2,402.62 | 11.59% |
| e5ee461797d486396616 | £8,534.07 | £2,366.88 | £8,921.99 | £6,167.19 | 16.22% |
| 8feb5f0f83e9432e0eda | £8,221.50 | £814.78 | £8,221.50 | £7,406.72 | 8.52% |

Showing 30 of 60 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 60 paths:** 14 wins, 14 losses, 32 ties vs buy-and-hold; beat cash on 31. Median excess 0.00% of capital; mean max drawdown 10.88%; sign-test p = 1.000.
**Not distinguishable from buy-and-hold on these paths; more paths or a better edge is needed.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
