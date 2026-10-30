// Exercise real popup callbacks with a fake provider, without opening Keychain.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const controls = new Map();
function element(id) {
  const state = { elementId: id, nodes: [], click: null, disabled: false };
  const proxy = new Proxy(state, {
    get(target, property) {
      if (property === "nodeState") return target;
      if (property in target) return target[property];
      return (...args) => {
        if (property === "child") target.nodes.push(args[0]);
        if (property === "children") target.nodes.push(...args[0]);
        if (property === "on_click") target.click = args[0];
        if (property === "disabled") target.disabled = args[0];
        return proxy;
      };
    },
  });
  // Keep the chainable method separate from the state flag.
  delete state.disabled;
  if (id) controls.set(id, state);
  return proxy;
}

const snapshots = new Map([["usage-bar.snapshot", {
  codex: { provider: "codex", windows: [{ label: "5h", used: 22 }], updated: 1 },
}]]);
const calls = [];
const pending = [];
const cx = { notify() {}, spawn(fn) { pending.push(fn(cx)); } };
let currentProvider = "cursor";
let settingsMode = false;
const source = fs.readFileSync(new URL("../mods/usage-bar/main.js", import.meta.url), "utf8")
  .replace(/^import[\s\S]*?from "[^"]+";\s*/gm, "")
  .replace("export default class UsageBar", "globalThis.UsageBar = class UsageBar");
const context = vm.createContext({
  View: class {}, div: () => element(), svg: () => element(), h_flex: () => element(), v_flex: () => element(),
  Button: { new: id => element(id) }, theme: () => ({}),
  props: () => ({ provider: settingsMode ? undefined : currentProvider, settings: settingsMode, overlay: "test" }),
  appHome: () => "/test", shared: key => snapshots.get(key),
  setShared: (key, value) => snapshots.set(key, value),
  exec: async (program, args) => {
    calls.push({ program, args });
    return { code: 0, stdout: JSON.stringify({ provider: args[1], windows: [{ label: "Total", used: 35 }], updated: 2 }) };
  }, closeOverlay() {}, openOverlay() {}, nextCommand() {},
});
vm.runInContext(source, context);

const popup = new context.UsageBar();
popup.init({}, cx);
popup.details();
controls.get("connect-provider").click({}, cx);
assert.equal(popup.busy.cursor, true, "connect should immediately report progress");
await Promise.all(pending.splice(0));
assert.equal(calls[0].program, "python3");
assert.equal(calls[0].args[1], "cursor");
assert.ok(calls[0].args.includes("--allow-keychain-prompt"), "connect must request the Keychain helper directly");
assert.equal(snapshots.get("usage-bar.snapshot").cursor.windows[0].used, 35);
assert.equal(snapshots.get("usage-bar.snapshot").codex.windows[0].used, 22, "connecting must retain other providers");
assert.equal(popup.busy.cursor, false);

const bar = new context.UsageBar();
bar.records = {};
bar.busy = {};
const chip = bar.chip("cursor", false, {});
assert.equal(controls.get("usage-cursor").nodes.at(-1).nodeState.nodes[0], "35%", "bar should reflect popup's new usage immediately");

popup.details();
calls.length = 0;
controls.get("refresh-provider").click({}, cx);
await Promise.all(pending.splice(0));
assert.equal(calls.length, 3, "Refresh all should call all three providers");
assert.ok(calls.every(call => !call.args.includes("--allow-keychain-prompt")), "ordinary refresh must not prompt");
calls.length = 0;
popup.details();
controls.get("copied-session").click({}, cx);
await Promise.all(pending.splice(0));
assert.ok(calls[0].args.includes("--cursor-session-from-clipboard"), "browser connection is an explicit clipboard action");

settingsMode = true;
const picker = new context.UsageBar();
picker.init({}, cx);
picker.render();
controls.get("show-cursor").click({}, cx);
assert.equal(snapshots.get("usage-bar.providers").includes("cursor"), false);
calls.length = 0;
bar.refreshAll(cx);
await Promise.all(pending.splice(0));
assert.deepEqual(calls.map(call => call.args[1]), ["codex", "claude"], "hidden providers must not be polled");
picker.render();
controls.get("show-cursor").click({}, cx);
await Promise.all(pending.splice(0));
assert.ok(snapshots.get("usage-bar.providers").includes("cursor"), "picker should persist re-enabling a provider");
console.log("Popup connect, progress, shared readings, and refresh callbacks passed (synthetic credentials).");
