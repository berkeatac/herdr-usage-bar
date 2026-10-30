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
        if (property === "when" && args[0]) return args[1](proxy);
        if (property === "child") target.nodes.push(args[0]);
        if (property === "children") target.nodes.push(...args[0]);
        if (property === "on_click") target.click = args[0];
        if (property === "on_change") target.change = args[0];
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
const timers = [];
const overlays = [];
const cx = { notify() {}, spawn(fn) { pending.push(fn(cx)); },
  timer: { every(ms, fn) { timers.push({ ms, fn }); } } };
let currentProvider = "cursor";
let settingsMode = false;
const source = fs.readFileSync(new URL("../mods/usage-bar/main.js", import.meta.url), "utf8")
  .replace(/^import[\s\S]*?from "[^"]+";\s*/gm, "")
  .replace("export default class UsageBar", "globalThis.UsageBar = class UsageBar");
const context = vm.createContext({
  View: class {}, div: () => element(), svg: () => element(), h_flex: () => element(), v_flex: () => element(),
  Button: { new: id => element(id) }, Checkbox: { new: id => element(id) }, theme: () => ({}),
  props: () => ({ provider: settingsMode ? undefined : currentProvider, settings: settingsMode, overlay: "test" }),
  appHome: () => "/test", shared: key => snapshots.get(key),
  setShared: (key, value) => snapshots.set(key, value),
  exec: async (program, args) => {
    calls.push({ program, args });
    return { code: 0, stdout: JSON.stringify({ provider: args[1], windows: [{ label: "Total", used: 35 }], updated: 2 }) };
  }, closeOverlay() {}, openOverlay(spec) { overlays.push(spec); }, nextCommand() {},
});
vm.runInContext(source, context);

const now = Date.now();
assert.equal(context.resetCountdown((now + (3 * 24 + 12) * 3600000) / 1000, now), "3d 12h");
assert.equal(context.resetCountdown(new Date(now + 135 * 60000).toISOString(), now), "2h 15m");
assert.equal(context.resetCountdown((now + 1000) / 1000, now), "1m");
assert.equal(context.resetCountdown((now - 1) / 1000, now), "Reset pending");
assert.equal(context.resetCountdown("invalid", now), null);
assert.equal(context.resetCountdown(null, now), null);

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
controls.clear();
popup.details();
assert.equal(controls.has("copied-session"), false, "connected Cursor must hide the browser login section");
assert.equal(controls.has("connect-provider"), false, "connected providers must hide Keychain retry");
bar.open("cursor");
assert.equal(overlays.at(-1).height, 320, "connected Cursor should use a compact popup");
snapshots.get("usage-bar.snapshot").cursor = { provider: "cursor", windows: [], error: "missing login" };
controls.clear();
popup.details();
controls.get("copied-session").click({}, cx);
await Promise.all(pending.splice(0));
assert.ok(calls[0].args.includes("--cursor-session-from-clipboard"), "browser connection is an explicit clipboard action");

snapshots.get("usage-bar.snapshot").codex.windows = [{ label: "5h", used: 22, reset: (Date.now() + 135 * 60000) / 1000 }];
bar.chip("codex", false, {});
assert.equal(controls.get("usage-codex").nodes.at(-1).nodeState.nodes[0], "(2h 15m)");
const beforeTimer = calls.length;
timers.find(timer => timer.ms === 60000).fn(cx);
assert.equal(calls.length, beforeTimer, "countdown ticks must not fetch usage");

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
settingsMode = false;
currentProvider = "codex";
snapshots.get("usage-bar.snapshot").codex.windows = [{ label: "5h", used: 22, reset: (Date.now() + 135 * 60000) / 1000 }];
const codexPopup = new context.UsageBar();
codexPopup.init({}, cx);
codexPopup.details();
controls.get("countdown-codex").change(false, cx);
assert.equal(context.showCountdown("codex"), false);
assert.equal(context.showCountdown("claude"), true, "provider countdown preferences must be independent");
bar.chip("codex", false, {});
assert.equal(controls.get("usage-codex").nodes.at(-1).nodeState.nodes[0], "22%", "unchecked countdown must disappear immediately");
codexPopup.details();
controls.get("countdown-codex").change(true, cx);
bar.chip("codex", false, {});
assert.equal(controls.get("usage-codex").nodes.at(-1).nodeState.nodes[0], "(2h 15m)");
assert.equal(context.showCountdown("cursor"), false, "Cursor retains its existing default without a bar countdown");
currentProvider = "cursor";
popup.details();
controls.get("countdown-cursor").change(true, cx);
snapshots.get("usage-bar.snapshot").cursor.windows[0].reset = (Date.now() + 135 * 60000) / 1000;
bar.chip("cursor", false, {});
assert.equal(controls.get("usage-cursor").nodes.at(-1).nodeState.nodes[0], "(2h 15m)", "Cursor's checkbox must also control its Total countdown");
function textOf(node) {
  return typeof node === "string" ? node : (node?.nodeState?.nodes || []).map(textOf).join(" ");
}
currentProvider = "codex";
for (const [credits, expected] of [
  [{ balance: "1234.5", has_credits: true }, "1234.5 credits"],
  [{ balance: "0", has_credits: false }, "0 credits"],
  [{ unlimited: true }, "Unlimited"],
  [{ has_credits: true }, "Available · balance not reported"],
  [{ has_credits: false }, "No remaining credits"],
  [null, "Not reported"],
]) {
  snapshots.get("usage-bar.snapshot").codex.credits = credits;
  assert.ok(textOf(codexPopup.details()).includes(expected), `Codex credits should show ${expected}`);
}
bar.open("codex");
assert.equal(overlays.at(-1).height, 450, "Codex popup needs room for credits");
console.log("Popup connect, progress, shared readings, and refresh callbacks passed (synthetic credentials).");
