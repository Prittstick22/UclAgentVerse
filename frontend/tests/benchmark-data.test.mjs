import assert from "node:assert/strict";
import { after, test } from "node:test";
import { createServer } from "vite";

const vite = await createServer({ configFile: false, server: { middlewareMode: true, hmr: false, ws: false } });
const { joinBenchmarkSeries, sp500ReturnSeries, sp500Key } = await vite.ssrLoadModule("/src/lib/benchmarkData.ts");
after(() => vite.close());

const point = (date, close_gbp) => ({ date, close_gbp });
const from = "2026-07-07";
const mid = "2026-07-08";
const to = "2026-07-09";
const tracker = {
  ticker: "VUAG.LSE", as_of: "2026-07-10",
  points: [point(to, 125), point(from, 100), point("2026-07-10", 500), point(mid, 75), point("2026-07-06", 20)],
};

test("the S&P 500 reference starts at zero and uses only adjusted prices in the report window", () => {
  assert.deepEqual(sp500ReturnSeries(tracker, from, to), [
    { date: from, [sp500Key]: 0 }, { date: mid, [sp500Key]: -.25 }, { date: to, [sp500Key]: .25 },
  ]);
});

test("the reference omits returns from incomplete, invalid or different instrument data", () => {
  assert.deepEqual(sp500ReturnSeries({ ...tracker, as_of: mid }, from, to), []);
  assert.deepEqual(sp500ReturnSeries({ ...tracker, ticker: "VWRP.LSE" }, from, to), []);
  assert.deepEqual(sp500ReturnSeries({ ...tracker, points: [point(from, 0), point(to, 125)] }, from, to), []);
  assert.deepEqual(sp500ReturnSeries({ ...tracker, points: [point(from, 100), point(mid, 125)] }, from, to), []);
  assert.deepEqual(sp500ReturnSeries({ ...tracker, points: [point(mid, 100), point(to, 125)] }, from, to), []);
});

test("benchmark balances align by date without inventing a missing balance", () => {
  assert.deepEqual(joinBenchmarkSeries({
    ours: [{ date: to, nav_gbp: 102 }, { date: from, nav_gbp: 100 }],
    buy_and_hold: [{ date: mid, nav_gbp: 110 }, { date: to, nav_gbp: 105 }],
  }), [{ date: from, ours: 100 }, { date: mid, buy_and_hold: 110 }, { date: to, ours: 102, buy_and_hold: 105 }]);
});
