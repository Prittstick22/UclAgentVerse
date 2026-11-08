# Finance project test report

**CHALLENGE (self-serve): hidden markets cases**

Dataset: 60 cases; seed: None; source: AgentVerse seeded generator v2 (hidden challenge).

Exact checks: **0 passed, 0 failed, 0 execution errors**.
Market simulations completed: **60**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `edd4a8c09960e26c9c355125e3a5e0a8eaba043a225994bd1c70e1795e2a2da3`
- Seed: fresh random; revealed in SEED-REVEAL.txt after this run
- Kit fingerprint: `5c90bf815848f4edd85bb2446e00382a24f003d936b3bad72f297a3b7885dad9` (compare with the organisers' published value)
- Project commit: `f9863279ad78922ad350b516480971f2eb35d5e3`, uncommitted changes: 1
- Provenance review: none flagged.

## Coverage

| Task / scenario family | Pass | Fail | Error | Simulated |
| --- | ---: | ---: | ---: | ---: |
| markets / falling | 0 | 0 | 0 | 10 |
| markets / flat | 0 | 0 | 0 | 10 |
| markets / jump | 0 | 0 | 0 | 10 |
| markets / regime_change | 0 | 0 | 0 | 10 |
| markets / rising | 0 | 0 | 0 | 10 |
| markets / volatile | 0 | 0 | 0 | 10 |

## Strategy results after costs

| Case | Final cash | Profit / loss | Buy-and-hold final | Cash baseline | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0461a272c33d783703c2 | £12,287.13 | £2,330.19 | £12,287.13 | £9,956.94 | 0.40% |
| b4c799cfd9f98b58a61c | £2,505.62 | -£477.34 | £1,969.70 | £2,982.96 | 16.01% |
| 59313fd0583616a80637 | £8,953.82 | -£57.12 | £8,953.82 | £9,010.94 | 0.63% |
| 4fdc32cc23d47a85e66a | £2,532.69 | -£397.14 | £2,537.21 | £2,929.83 | 29.35% |
| d740848ca743d2f7e06a | £8,049.94 | £1,514.57 | £6,120.44 | £6,535.37 | 10.93% |
| e361dbc9413d88019c6c | £5,190.87 | -£2,235.62 | £5,055.21 | £7,426.49 | 30.83% |
| 2bdf7e94327e3dda390e | £6,600.37 | £1,229.10 | £6,600.37 | £5,371.27 | 0.65% |
| e18cb8426c3d4648fd48 | £8,565.61 | -£1,008.62 | £8,565.61 | £9,574.23 | 10.53% |
| 61ae77fd39a5d1e6a3ae | £7,919.31 | -£43.64 | £7,919.31 | £7,962.95 | 0.54% |
| fa54d2ede0404cbd6bad | £3,861.75 | -£1,035.05 | £1,641.54 | £4,896.80 | 21.13% |
| 04a8a98dadf642112562 | £3,980.23 | £286.34 | £3,706.39 | £3,693.89 | 16.76% |
| 713aa50111e68c7c6906 | £2,321.08 | £491.60 | £2,321.08 | £1,829.48 | 2.23% |
| f98ef6e72032dd9094bd | £4,129.51 | £1,253.56 | £4,129.51 | £2,875.95 | 0.79% |
| ac7b2580ff16f4c63472 | £5,584.10 | -£678.91 | £5,584.10 | £6,263.01 | 10.91% |
| e614350bb0194e0f3deb | £5,387.15 | -£32.10 | £5,387.15 | £5,419.25 | 0.59% |
| 7ad5e35335e44277fa42 | £5,746.89 | £138.34 | £6,745.67 | £5,608.55 | 20.16% |
| 3d809da807ddc9fe0f78 | £7,824.56 | £579.72 | £7,255.64 | £7,244.84 | 17.75% |
| 419b7ae50a90668bb135 | £5,797.20 | -£2,431.90 | £5,810.88 | £8,229.10 | 31.28% |
| a0cca26d1fb2df679d06 | £9,717.51 | £3,330.70 | £9,717.51 | £6,386.81 | 0.47% |
| 7e6eb20eb2e7b4b10eb0 | £3,000.73 | -£604.20 | £2,529.19 | £3,604.93 | 16.79% |
| 0fc7fda1d1e7aaf2fd1c | £6,297.17 | -£45.48 | £6,297.17 | £6,342.65 | 0.71% |
| cad89193bcebdd67c41e | £8,914.79 | £964.66 | £7,750.63 | £7,950.13 | 19.89% |
| e3a8450d4f161533448d | £8,655.20 | £1,402.98 | £7,486.28 | £7,252.22 | 16.05% |
| 72dcdaa8308347c954e8 | £8,360.34 | £1,586.36 | £8,378.26 | £6,773.98 | 3.75% |
| f23a037244ebe8ae79de | £5,277.28 | £1,133.04 | £5,277.28 | £4,144.24 | 0.30% |
| a983e251688788c98eef | £2,569.84 | -£528.30 | £2,154.00 | £3,098.14 | 17.05% |
| 9ec42f9fba26465a78db | £4,962.31 | -£14.20 | £4,962.31 | £4,976.51 | 0.28% |
| 8ad811712e2f48800397 | £5,206.75 | £39.90 | £4,429.15 | £5,166.85 | 15.96% |
| e451a4238d73072a5082 | £966.26 | -£59.73 | £950.86 | £1,025.99 | 16.62% |
| 74f825608f7c4b5d1e34 | £11,461.32 | £2,067.60 | £11,557.50 | £9,393.72 | 7.10% |

Showing 30 of 60 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 60 paths:** 24 wins, 11 losses, 25 ties vs buy-and-hold; beat cash on 28. Median excess 0.00% of capital; mean max drawdown 11.96%; sign-test p = 0.041.
**Not distinguishable from buy-and-hold on these paths; more paths or a better edge is needed.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
