import { View, div } from "gpui-kit";
import { Button, h_flex, v_flex } from "gpui-base";
import { appHome, exec, theme, props, openOverlay, closeOverlay,
  shared, setShared, nextCommand, run } from "herdr";

const NAMES = { codex: "Codex", claude: "Claude", cursor: "Cursor" };
const ORDER = ["codex", "claude", "cursor"];
const SNAPSHOT = "usage-bar.snapshot";

function percent(n) {
  if (n > 0 && n < 1) return "<1%";
  if (n < 100 && n > 99) return ">99%";
  return `${Math.round(n)}%`;
}

function resetText(value) {
  if (!value) return "Reset time unavailable";
  const date = new Date(typeof value === "number" ? value * 1000 : value);
  return Number.isNaN(date.getTime()) ? "Reset time unavailable" : `Resets ${date.toLocaleString()}`;
}

function usageColor(n, t) {
  return n >= 95 ? t.blocked : n >= 75 ? t.working : t.foreground;
}

function control(id, text, action, t) {
  return Button.new(id).px(10).py(6).rounded(5).cursor_pointer()
    .text_color(t.foreground).bg(t.surface).hover(s => s.bg(t.raised))
    .accessibility_label(text).child(text).on_click(action);
}

export default class UsageBar extends View {
  init(_props, cx) {
    this.records = {};
    this.busy = {};
    this.width = 1200;
    this.detail = props()?.provider || null;
    if (this.detail) return;
    setShared(SNAPSHOT, {});
    this.refreshAll(cx);
    cx.timer.every(120000, cx => this.refreshAll(cx));
    cx.spawn(async cx => {
      for (;;) {
        const command = await nextCommand();
        if (command === "refresh") this.refreshAll(cx);
        const provider = command.replace("connect-", "");
        if (command.startsWith("connect-") && ORDER.includes(provider)) {
          this.refresh(provider, cx, true);
        }
      }
    });
  }

  refreshAll(cx) {
    for (const provider of ORDER) this.refresh(provider, cx);
  }

  refresh(provider, cx, allowKeychain = false) {
    if (this.busy[provider]) return;
    this.busy[provider] = true;
    cx.spawn(async cx => {
      try {
        const args = [`${appHome()}/mods/usage-bar/collect.py`, provider];
        if (allowKeychain) args.push("--allow-keychain-prompt");
        const result = await exec("python3", args);
        if (result.code !== 0) throw new Error("helper");
        const record = JSON.parse(result.stdout);
        if (record.provider !== provider || !Array.isArray(record.windows)) throw new Error("data");
        this.records[provider] = record;
      } catch (_) {
        this.records[provider] = { provider, windows: [], updated: null,
          error: "Usage helper unavailable. Install Python 3 and check the mod files." };
      }
      this.busy[provider] = false;
      setShared(SNAPSHOT, this.records);
      cx.notify();
    });
  }

  open(provider) {
    openOverlay({ mod: "usage-bar", props: { provider }, kind: "popup", width: 440, height: 330 });
  }

  chip(provider, compact, t) {
    const record = this.records[provider];
    const windows = record?.windows || [];
    const title = `${NAMES[provider]} usage — ${record?.error || windows.map(w =>
      `${w.label}: ${percent(w.used)} used. ${resetText(w.reset)}`).join("; ") || "Loading"}. Click for details.`;
    const chip = Button.new(`usage-${provider}`).h_flex().items_center().gap(compact ? 5 : 7)
      .h(24).px(compact ? 6 : 8).rounded(4).flex_shrink_0().cursor_pointer()
      .hover(s => s.bg(t.raised)).accessibility_label(title).tooltip(title)
      .on_click(() => this.open(provider))
      .child(div().font_semibold().text_color(t.foreground).child(NAMES[provider]));
    if (!record) return chip.child(div().text_color(t.dim).child("…"));
    if (!windows.length) return chip.child(div().text_color(t.dim).child("—"));
    windows.forEach((w, index) => {
      if (index) chip.child(div().text_color(t.dim).child("·"));
      chip.child(div().text_color(t.muted).child(w.label));
      chip.child(div().text_color(usageColor(w.used, t)).child(percent(w.used)));
    });
    return chip;
  }

  details() {
    const t = theme();
    const provider = this.detail;
    const record = shared(SNAPSHOT)?.[provider];
    const body = v_flex().size_full().p(18).gap(14).bg(t.chrome)
      .text_size(12).text_color(t.foreground)
      .child(h_flex().items_center().justify_between()
        .child(div().text_size(16).font_semibold().child(`${NAMES[provider]} usage`))
        .child(control("close", "Close", () => closeOverlay(props().overlay), t)))
      .child(div().text_color(t.muted).child(provider === "cursor"
        ? "Total is included plan usage for this billing cycle."
        : "Percentages show quota used in each rolling window."));
    if (record?.windows?.length) {
      for (const w of record.windows) {
        body.child(v_flex().gap(5)
          .child(h_flex().justify_between()
            .child(div().child(w.label === "7d" ? "Weekly · 7 days" : w.label === "5h" ? "Current · 5 hours" : w.label))
            .child(div().font_semibold().text_color(usageColor(w.used, t)).child(`${percent(w.used)} used`)))
          .child(div().h(4).w_full().rounded(2).bg(t.border)
            .child(div().h(4).w(395 * Math.min(100, w.used) / 100).rounded(2).bg(usageColor(w.used, t))))
          .child(div().text_size(11).text_color(t.dim).child(resetText(w.reset))));
      }
      body.child(div().text_size(11).text_color(t.dim)
        .child(`Updated ${new Date(record.updated * 1000).toLocaleTimeString()} · refreshes every 2 minutes`));
    } else {
      body.child(div().text_color(t.muted).child(record?.error || "Reading usage…"));
    }
    body.child(div().flex_1());
    const actions = h_flex().gap(8).child(control("refresh-provider", "Refresh all", () => run("usage-bar.refresh"), t));
    if (provider === "claude" || provider === "cursor") {
      actions.child(control("connect-provider", "Allow Keychain access", () => run(`usage-bar.connect-${provider}`), t)
        .tooltip("Ask macOS to allow Python to read this provider's sign-in item. Automatic refresh never prompts."));
    }
    return body.child(actions);
  }

  render() {
    if (this.detail) return this.details();
    const t = theme();
    const compact = this.width < 700;
    return h_flex().id("usage-bar").size_full().items_center().px(6).gap(2)
      .bg(t.chrome).border_t(1).border_color(t.border).text_size(11.5)
      .on_size_change((size, cx) => {
        if (this.width !== size.width) { this.width = size.width; cx.notify(); }
      })
      .child(h_flex().id("usage-providers").items_center().gap(2).flex_1().overflow_x_scroll()
        .children(ORDER.map(provider => this.chip(provider, compact, t)))
        .child(Button.new("refresh-usage").px(8).h(24).flex_shrink_0().rounded(4).cursor_pointer()
          .text_color(t.muted).hover(s => s.bg(t.raised)).child("↻")
          .accessibility_label("Refresh usage for Codex, Claude and Cursor")
          .tooltip("Refresh usage · automatic refresh every 2 minutes")
          .on_click((_event, cx) => this.refreshAll(cx))))
      .when(this.width > 760, el => el.child(div().px(8).text_color(t.dim).child("quota used")));
  }
}
