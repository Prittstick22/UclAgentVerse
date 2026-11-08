import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

function streamClient() {
  let connection;
  class FakeEventSource {
    closed = false;
    listeners = new Map();
    constructor(url) { this.url = url; connection = this; }
    addEventListener(type, handler) { this.listeners.set(type, handler); }
    close() { this.closed = true; }
    emit(type) { this.listeners.get(type)?.({ data: JSON.stringify({ type }) }); }
  }
  const source = readFileSync(new URL("../src/lib/sse.ts", import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } });
  const exports = {};
  runInNewContext(compiled.outputText, {
    exports, EventSource: FakeEventSource,
    require: () => ({ MOCK: false }),
  });
  const received = [];
  const stop = exports.subscribeRun("recorded-run", event => received.push(event.type));
  return { connection, received, stop };
}

test("completion keeps trailing gate/approval frames and native retry until caller cleanup", () => {
  const { connection, received, stop } = streamClient();
  connection.emit("run.completed");
  assert.equal(connection.closed, false);
  connection.emit("gate.verdict");
  connection.emit("approval.decided");
  assert.deepEqual(received, ["run.completed", "gate.verdict", "approval.decided"]);
  assert.equal(connection.onerror, undefined);
  stop();
  assert.equal(connection.closed, true);
});

test("pre-completion errors retain native retry; caller cleanup still closes", () => {
  const { connection, stop } = streamClient();
  connection.onerror?.();
  assert.equal(connection.closed, false);
  stop();
  assert.equal(connection.closed, true);
});

test("workspace retains trailing evidence and unsubscribes on unmount", async () => {
  const source = readFileSync(new URL("../src/lib/useRunEvents.ts", import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  });
  const exports = {};
  const states = [[]];
  const effects = [];
  let stateIndex = 0;
  let receive;
  let stopped = 0;
  runInNewContext(compiled.outputText, {
    exports,
    require: name => {
      if (name === "react") return {
        useState: () => {
          const index = stateIndex++;
          return [states[index], value => {
            states[index] = typeof value === "function" ? value(states[index]) : value;
          }];
        },
        useEffect: effect => effects.push(effect),
      };
      if (name === "./sse") return {
        subscribeRun: (_id, callback) => { receive = callback; return () => { stopped++; }; },
      };
      throw new Error(`Unexpected test import: ${name}`);
    },
  });
  exports.useRunEvents("recorded-run", true);
  const cleanup = effects[0]();
  receive({ id: "completed", type: "run.completed" });
  receive({ id: "gate", type: "gate.verdict" });
  receive({ id: "gate", type: "gate.verdict" });
  await Promise.resolve();
  assert.equal(stopped, 0);
  assert.deepEqual(Array.from(states[0], event => event.type), ["run.completed", "gate.verdict"]);
  cleanup();
  assert.equal(stopped, 1);
});
