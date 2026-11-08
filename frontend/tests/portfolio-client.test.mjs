import assert from "node:assert/strict";
import { after, afterEach, test } from "node:test";
import { createServer } from "vite";

process.env.VITE_MOCK = "0";
const vite = await createServer({ configFile: false, server: { middlewareMode: true, hmr: false } });
const { api, attachApiFeedback, get, ApiError } = await vite.ssrLoadModule("/src/lib/api.ts");
const { portfolioQueries } = await vite.ssrLoadModule("/src/lib/portfolioQueries.ts");
const originalFetch = globalThis.fetch;

afterEach(() => { globalThis.fetch = originalFetch; });
after(() => vite.close());

test("protected build retries once, then reuses the accepted passcode only for protected requests", async () => {
  const requests = [];
  const prompts = [];
  const errors = [];
  const detach = attachApiFeedback({
    requestPasscode: async (rejected) => { prompts.push(rejected); return "local-test-passcode"; },
    showError: (error) => errors.push(error),
  });
  globalThis.fetch = async (path, { headers }) => {
    const credential = headers?.get("X-Demo-Passcode");
    requests.push([path, credential ?? null]);
    if (path === "/api/portfolio/build" && !credential) {
      return Response.json({ error: { code: "unauthorized", message: "Passcode required" } }, { status: 401 });
    }
    return Response.json({ run_id: "test-run" });
  };
  try {
    await api.build();
    await api.build();
    await api.health();
    assert.deepEqual(prompts, [false]);
    assert.deepEqual(errors, []);
    assert.deepEqual(requests, [
      ["/api/portfolio/build", null],
      ["/api/portfolio/build", "local-test-passcode"],
      ["/api/portfolio/build", "local-test-passcode"],
      ["/api/health", null],
    ]);
  } finally {
    detach();
  }
});

test("structured rate-limit errors reach the shell and an aborted read stays silent", async () => {
  const errors = [];
  const detach = attachApiFeedback({ showError: (error) => errors.push(error) });
  globalThis.fetch = async () => Response.json({ error: { code: "rate_limited" } }, { status: 429 });
  try {
    await assert.rejects(api.health(), (error) => error instanceof ApiError && error.code === "rate_limited");
    await assert.rejects(api.health(AbortSignal.abort()), { name: "AbortError" });
    assert.equal(errors.length, 1);
    assert.match(errors[0].message, /Too many requests/);
  } finally {
    detach();
  }
});

test("demo selection falls back to the profile served by older backends without a global error", async () => {
  const errors = [];
  const detach = attachApiFeedback({ showError: (error) => errors.push(error) });
  const { signal } = new AbortController();
  try {
    for (const legacyStatus of [200, 404]) {
      const requests = [];
      globalThis.fetch = async (path) => {
        requests.push(path);
        if (path === "/api/profile/demos") {
          return new Response("<!doctype html>", { status: legacyStatus, headers: { "Content-Type": "text/html" } });
        }
        return Response.json({ name: "Caroline" });
      };
      assert.deepEqual(await api.demos(signal), { caroline: { name: "Caroline" } });
      assert.deepEqual(requests, ["/api/profile/demos", "/api/profile/demo"]);
    }
    assert.deepEqual(errors, []);
  } finally {
    detach();
  }
});

test("portfolio P&L requires the requested period and correlations use held symbols", async () => {
  const requests = [];
  globalThis.fetch = async (path, { signal }) => {
    assert.ok(signal instanceof AbortSignal);
    requests.push(path);
    return Response.json({ period: "1m" });
  };
  const { signal } = new AbortController();
  assert.equal((await portfolioQueries.pnl("1m", signal)).period, "1m");
  await assert.rejects(portfolioQueries.pnl("3m", signal), /selected period is unavailable/);
  await portfolioQueries.correlations("IGLS.LSE,VUAG.LSE", signal);
  assert.deepEqual(requests, [
    "/api/portfolio/pnl?period=1m",
    "/api/portfolio/pnl?period=3m",
    "/api/risk/correlation?tickers=IGLS.LSE%2CVUAG.LSE",
  ]);
});
