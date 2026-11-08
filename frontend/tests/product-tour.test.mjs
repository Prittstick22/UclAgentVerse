import assert from "node:assert/strict";
import { after, test } from "node:test";
import { createServer } from "vite";

const vite = await createServer({ configFile: false, server: { middlewareMode: true, hmr: false, ws: false } });
const { placeTourCard, tourSteps } = await vite.ssrLoadModule("/src/lib/productTour.ts");
after(() => vite.close());

test("the tour follows the correct investigation and gives demo and live distinct next steps", () => {
  const demo = tourSteps({ mode: "historical", room: "/timeline" });
  const live = tourSteps({ mode: "live", room: "/runs/run_live?live=1" });
  for (const steps of [demo, live]) {
    assert.deepEqual(steps.slice(0, 2).map(step => step.path), ["/", "/workspace"]);
    assert.deepEqual(steps.slice(0, 2).map(step => step.targets[0]), ["dashboard", "agents-intro"]);
    assert.deepEqual(steps.slice(2, 6).map(step => step.id), ["playback", "models", "evidence", "verification"]);
    assert.equal(steps[5].targets[0], "assurance");
    assert.deepEqual(steps.slice(6, 10).map(step => step.id), ["decisions", "benchmarks", "holdings", "news"]);
    assert.match(steps[4].body, /CVXPY.*trading costs.*Ledoit–Wolf/);
  }
  assert.ok(demo.slice(2, 6).every(step => step.path === "/timeline"));
  assert.ok(live.slice(2, 6).every(step => step.path === "/runs/run_live?live=1"));
  assert.match(demo[1].body, /scheduled reviews.*drift.*Gemini 4 Argon/);
  assert.match(live[1].body, /Check portfolio now.*Gemini 4 Argon/);
  assert.equal(demo[2].targets[0], "replay");
  assert.equal(live[2].targets[0], "run-intro");
  assert.equal(demo.at(-1).targets[0], "profile");
  assert.equal(live.at(-1).targets[0], "portfolio-check");
});

test("the callout picks a side with room or stays within the viewport", () => {
  const viewport = { width: 1280, height: 800 };
  const card = { width: 342, height: 230 };
  const target = { left: 40, top: 80, width: 100, height: 30 };
  assert.equal(placeTourCard(target, viewport, card).side, "right");
  assert.equal(placeTourCard({ ...target, left: 1140 }, viewport, card).side, "left");
  const narrow = { width: 420, height: 680 };
  const placement = placeTourCard({ ...target, left: 160, top: 400 }, narrow, card);
  assert.equal(placement.side, "above");
  assert.ok(placement.left >= 16 && placement.left + card.width <= narrow.width - 16);
  assert.deepEqual(placeTourCard(null, viewport, card), { left: 469, top: 285, side: "none" });
});
