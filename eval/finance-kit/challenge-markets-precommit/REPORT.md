# Finance project test report

**CHALLENGE (self-serve): hidden markets cases**

Dataset: 60 cases; seed: None; source: AgentVerse seeded generator v2 (hidden challenge).

Exact checks: **0 passed, 0 failed, 0 execution errors**.
Market simulations completed: **60**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `00fd2603513b8ff8fc64782b28402471907259703ec9cbed6a51d3f5db3d7e18`
- Seed: fresh random; revealed in SEED-REVEAL.txt after this run
- Kit fingerprint: `5c90bf815848f4edd85bb2446e00382a24f003d936b3bad72f297a3b7885dad9` (compare with the organisers' published value)
- Project commit: `d1d89624c744282e2862ee1f4c8915c1dc4fc1b7`, uncommitted changes: 1
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
| 62c3e6ce3aeb681535ba | £15,802.58 | £6,621.12 | £15,802.58 | £9,181.46 | 1.04% |
| 995fa4e620bbf70d5e5a | £5,056.10 | -£989.84 | £4,378.10 | £6,045.94 | 16.37% |
| 58942e18e1f6b8d9a025 | £5,870.39 | -£11.90 | £5,870.39 | £5,882.29 | 0.20% |
| 64fe20c06ac3ace1eb0c | £3,682.74 | -£702.88 | £2,986.20 | £4,385.62 | 17.91% |
| def306f8d134297af415 | £5,083.37 | £1,378.50 | £3,775.53 | £3,704.87 | 6.58% |
| 99827ef8f690ef537ac2 | £5,514.76 | £1,170.09 | £5,514.76 | £4,344.67 | 2.14% |
| 868649a497d913b9f48e | £10,813.29 | £2,800.48 | £10,813.29 | £8,012.81 | 0.40% |
| a200673e0ce993d36264 | £6,682.78 | -£1,105.39 | £5,048.89 | £7,788.17 | 14.19% |
| 83277db04e5292a4b31c | £7,003.90 | -£51.28 | £7,003.90 | £7,055.18 | 0.72% |
| fb9709df14c95e53315d | £3,831.40 | -£1,228.74 | £5,023.32 | £5,060.14 | 32.30% |
| a9836346ccc00777a6a5 | £10,297.58 | £2,134.21 | £7,675.51 | £8,163.37 | 9.89% |
| 0acb79705c232d046131 | £11,336.87 | £2,458.37 | £11,336.87 | £8,878.50 | 1.71% |
| 45b736204ad4c03c489c | £2,968.30 | £692.75 | £2,968.30 | £2,275.55 | 0.52% |
| 1013d6100579c0b2ca02 | £1,113.47 | -£192.50 | £826.91 | £1,305.97 | 14.74% |
| 9ba4ae95480665d2e5ea | £7,168.45 | -£6.64 | £7,168.45 | £7,175.09 | 0.09% |
| 19f27e0bd0587f7334eb | £1,333.71 | -£209.59 | £1,602.26 | £1,543.30 | 24.71% |
| 99932cb8a3e76d2a0f4a | £2,024.16 | £8.41 | £2,016.56 | £2,015.75 | 17.17% |
| 68fb47e556941414f05d | £6,618.50 | -£3,294.91 | £6,618.50 | £9,913.41 | 33.23% |
| db0d6b166bc01adc9c9d | £9,592.12 | £607.28 | £9,592.12 | £8,984.84 | 0.51% |
| 886cac19e105530be54e | £7,570.31 | -£1,398.23 | £7,517.91 | £8,968.54 | 15.59% |
| f31846d3a1b3279ff931 | £5,380.10 | -£25.70 | £5,380.10 | £5,405.80 | 0.47% |
| 29bda467f0884ecdf87a | £2,472.77 | -£695.66 | £3,081.73 | £3,168.43 | 31.47% |
| babfac0753994b74303d | £3,837.73 | -£141.90 | £3,703.31 | £3,979.63 | 16.42% |
| ca4d7e5bd89a5b889b9d | £12,747.96 | £2,816.20 | £12,482.96 | £9,931.76 | 2.36% |
| 524b22111e92eee2fa53 | £2,205.42 | £606.68 | £2,205.42 | £1,598.74 | 0.39% |
| 3f8eb9505432cd1a3e2c | £5,241.26 | -£1,053.18 | £3,994.42 | £6,294.44 | 16.78% |
| edfc3ac432c62e3adbcb | £1,438.85 | -£5.82 | £1,438.85 | £1,444.67 | 0.40% |
| a8dde340baa4f5a95ccd | £3,019.86 | -£579.50 | £2,779.62 | £3,599.36 | 17.57% |
| 238319929e46920ac742 | £5,163.44 | -£141.49 | £4,985.57 | £5,304.93 | 17.68% |
| fecccf764571f38ee9cb | £10,852.47 | £2,124.06 | £10,893.39 | £8,728.41 | 3.55% |

Showing 30 of 60 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 60 paths:** 24 wins, 6 losses, 30 ties vs buy-and-hold; beat cash on 26. Median excess 0.00% of capital; mean max drawdown 9.98%; sign-test p = 0.001.
**Not distinguishable from buy-and-hold on these paths; more paths or a better edge is needed.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
