import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const json = async (path) => JSON.parse(await readFile(new URL(path, import.meta.url), "utf8"));

test("every stock in the catalogue and both ETF issuers have a bundled logo", async () => {
  const { instruments } = await json("../../backend/app/config/catalogue.json");
  const sources = await json("../scripts/holding-logo-sources.json");
  const filenames = Object.keys(sources);
  const identifiers = filenames.map(filename => filename.slice(0, filename.lastIndexOf(".")));
  assert.equal(new Set(identifiers).size, identifiers.length);
  for (const instrument of instruments) {
    if (instrument.kind === "stock") assert.ok(identifiers.includes(instrument.ticker), instrument.ticker);
  }
  assert.ok(identifiers.includes("vanguard"));
  assert.ok(identifiers.includes("ishares"));
  for (const [filename, url] of Object.entries(sources)) {
    assert.equal(new URL(url).protocol, "https:");
    const image = await readFile(new URL("../src/assets/holding-logos/" + filename, import.meta.url));
    assert.ok(image.length > 0 && image.length <= 128 * 1024, filename);
  }
});
