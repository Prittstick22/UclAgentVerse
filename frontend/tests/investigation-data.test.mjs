import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { after, test } from "node:test";
import { createServer } from "vite";

const vite = await createServer({ configFile: false, server: { middlewareMode: true, hmr: false, ws: false } });
const { investigationTitle, publicNarrative, publicSteps, recordedValuePoints, searchForStep, searchScope, triggerNewsIds } = await vite.ssrLoadModule("/src/lib/investigation.ts");
after(() => vite.close());

const event = (seq, type, payload, overrides = {}) => ({
  id: "event-" + seq, seq, type, payload, agent_id: "lead", role: "lead", evidence_ids: [], ...overrides,
});

test("recorded triggers keep readable copy and retain article IDs for evidence lookup only", () => {
  const id = "news_finnhub_fd1837630b320f604902";
  const news = `**AAPL.US news (3 event headlines today), e.g. 'Apple Soars 6% After Earnings' (${id})**`;
  assert.equal(investigationTitle(news, "news"), "AAPL news review");
  assert.equal(investigationTitle("AZN.LSE rose 7.0% today; " + news, "price_move"), "AZN rose 7.0% today · AAPL news");
  assert.deepEqual(triggerNewsIds(news), [id]);
  assert.equal(publicNarrative(`**Apple kept its guidance** [${id}, case:AAPL.US:v2].`), "Apple kept its guidance.");
  assert.equal(publicNarrative("The company reported 6.0% growth."), "The company reported 6.0% growth.");
});

test("searches expose the actual query or ticker scope for the matching agent only", () => {
  const news = event(1, "tool.call", { tool: "search_news", args: { tickers: ["VUAG.LSE"], since: "2026-07-07T09:00:00Z", query: "unused" } });
  const other = event(2, "tool.call", { tool: "search_news", args: { tickers: ["IGLS.LSE"] } }, { agent_id: "risk" });
  const result = event(3, "tool.result", { tool: "search_news", ok: true });
  const web = event(4, "tool.call", { tool: "web_search", args: { query: "UK gilt yields September" } });
  assert.deepEqual(searchForStep(result, [news, other, result]), [
    { label: "Looking at", value: "VUAG" }, { label: "Since", value: "2026-07-07" },
  ]);
  assert.deepEqual(searchScope(web), [{ label: "Search terms", value: "UK gilt yields September" }]);
  assert.deepEqual(searchForStep({ ...result, status: "denied" }, [news]), []);
});

test("the report sorts observable steps and avoids debug payloads, usage counts and unsafe text", () => {
  const events = [
    event(5, "run.completed", { outcome: "maintain", tokens: 330, cost_estimate_usd: 0.77 }),
    event(1, "tool.call", { tool: "search_news", args: { tickers: ["VUAG.LSE"], debug_secret: "ignore-me" } }),
    event(2, "tool.result", { tool: "search_news", ok: false, summary: "internal stack trace" }),
    event(3, "calc.result", { name: "exposure", outputs: { total: null, known_total: .1 } }),
    event(4, "content.quarantined", { reason: "unsafe instruction" }, { evidence_ids: ["bad-source"] }),
  ];
  const steps = publicSteps(events);
  assert.deepEqual(steps.map(step => step.id), ["event-1", "event-2", "event-3", "event-4", "event-5"]);
  assert.equal(steps[3].sources.length, 0);
  assert.match(steps[2].notes.join(" "), /could not be measured/);
  assert.deepEqual(steps[2].facts, [{ label: "Known portion of exposure", value: "10%" }]);
  assert.doesNotMatch(JSON.stringify(steps), /ignore-me|stack trace|unsafe instruction|330|0\.77/);
});

test("report charts sort recorded prices and exclude invalid and future observations", () => {
  const values = [
    ["2026-07-07T17:00:00Z", 102], ["2026-07-03", 100], ["2026-07-08", 105], ["not a date", 106],
    ["2026-07-05", "101"], ["2026-07-06", NaN], ["2026-07-06", 0],
  ];
  assert.deepEqual(recordedValuePoints(values, "2026-07-07").map(({ date, value }) => [date, value]), [
    ["2026-07-03", 100], ["2026-07-07", 102],
  ]);
  assert.deepEqual(recordedValuePoints(undefined, "2026-07-07"), []);
  const [step] = publicSteps([event(1, "calc.result", { name: "backtest", outputs: { nav: values } }, { as_of: "2026-07-07" })]);
  assert.deepEqual(step.tables[0].rows, [["2026-07-03", "£100.00"], ["2026-07-07", "£102.00"]]);
});

test("older construction fixtures produce calculations, findings, and a conclusion", async () => {
  const fixture = JSON.parse(await readFile(new URL("../../fixtures/events_construction.json", import.meta.url), "utf8"));
  const steps = publicSteps(Array.isArray(fixture) ? fixture : fixture.items);
  assert.ok(steps.some(step => step.tables.some(table => table.heading === "Candidate allocation")));
  assert.ok(steps.some(step => step.heading === "Finding" && step.notes.length));
  assert.equal(steps.at(-1).heading, "Starting portfolio prepared");
});
