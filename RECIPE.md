# Usage Bar

Codex, Claude and Cursor usage sits at the left of Herdr's bottom bar. A small token icon opens a provider picker; selections are remembered. Codex and Claude show their current and weekly quota windows when reported, while Cursor shows its included billing-cycle Total. Percentages mean used. The adjacent refresh arrow retries visible providers. An exclamation mark means the reading is unavailable; clicking explains why and what to do next. The preview is a crop of the real running mod, with the user’s selected providers and live Codex/Cursor readings.

![Usage Bar](preview.png)

## What you see

A 28px strip, left to right: a 24px token-picker button with a 14px outlined hexagonal token, the selected providers in Codex/Claude/Cursor order, an immediately adjacent refresh arrow, flexible space, then a dim `quota used` caption when the block is wider than 760px. Use the UI font at 11.5px, a chrome background, a top border, foreground semibold provider names, muted window labels and dim separators. Ordinary percentages use foreground; 75% and above use the working color, 95% and above use blocked. Provider buttons have 8px horizontal padding, reduced to 6px below 700px width. The provider group scrolls horizontally when necessary.

The icon opens a 310×275px picker with 16px padding, a title, Close, three selectable provider buttons with checkmarks and a reminder that hidden providers stop automatic refresh. Selecting none leaves the icon, a `Choose providers` hint and the arrow.

Provider details open in a 480px-wide popup, 380px high normally, 320px for connected Cursor or 500px for disconnected Cursor, with 18px padding and vertical overflow scrolling. Show title and Close, an explanation, available quota percentages and 4px meters, reset countdowns, exact local timestamps and update time. For a failed reading show a short status heading, a specific explanation and an actionable next step. Refresh all is always available. Retry Keychain appears only for disconnected Claude/Cursor. Disconnected Cursor also has a separate Connect without Keychain section explaining how to copy the browser session and a Use copied browser session button.

## How it behaves

Read selected providers independently on first display and every two minutes. Hiding a provider removes it and stops subsequent automatic reads; enabling it starts a read immediately. Save the selected provider names across layouts and restarts. Every provider popup includes a native checkbox labeled Show countdowns in bar. Persist its boolean independently per provider in shared key usage-bar.countdowns and update the bar immediately without a fetch. Codex/Claude default on; Cursor defaults off, but checking it adds the billing-cycle Total countdown. Popup countdowns and exact timestamps remain available regardless of this bar preference. Successful readings hide the sign-in controls, including Cursor’s browser-session section. The picker does not change sign-ins. Native buttons support pointer and keyboard activation. Hovers explain percentages, reset times and actions. Escape or Close dismisses popups.

Show an ellipsis for the initial pending read, `!` for a failure and a real `0%` for actual zero. Percentages between zero and one are `<1%`, between 99 and 100 are `>99%`. Keep reported values over 100% visible while clamping meter widths. A failed read clears previous numbers for that provider. Other providers retain their readings. Agent states working, blocked, done and idle do not affect quota displays; threshold colors describe consumption only.

Countdowns show remaining days/hours (3d 12h), hours/minutes (2h 15m), or minutes below an hour. Keep the exact local reset timestamp below each popup countdown. When enabled for that provider, show the countdown in parentheses after each percentage in the bar. Missing or malformed reset times have no countdown; elapsed reset times say Reset pending until the next provider reading. A 60000ms timer redraws the bar and detail popups without making provider requests.

Popup actions run directly in that popup's copy. Show Connecting… or Refreshing… while its work is pending and disable duplicate actions there. Publish sanitized results so the bar updates immediately. Never route popup actions through an app command that may not reach the intended copy.

Automatic Keychain reads never prompt. Retry Keychain explicitly permits a macOS prompt, which the person handles. Differentiate missing keys, locked Keychain, denied access, cancellation, missing account sign-in, expired credentials, missing usage scope, HTTP 401, HTTP 403, rate limits, network errors and successful responses without quota. A permission grant is not a login, and an inaccessible credential does not establish an inactive subscription.

Cursor's copied-session action reads the clipboard only when clicked. Instructions identify cursor.com's WorkosCursorSessionToken cookie value in browser DevTools. Validate its JWT expiry and subject, check it with Cursor, and save only an accepted session in an owner-only local file for subsequent automatic refresh. Invalid clipboard contents must never be echoed or saved. Ordinary refresh never reads the clipboard. Never ask the person to paste credentials into chat.

## Built from

Ship `mods/usage-bar/main.js`, `collect.py`, `mod.json` and `tokens.svg`, plus this recipe, preview, README, installer and tests. No `layouts/` directory or keys.json snippet is needed. The manifest has title Usage Bar, `place: "none"`, size 28, and a 440×330 overlay default. The main script overrides popup dimensions.

The default export is a gpui-kit View using div/svg and gpui-base flex containers and native Buttons. No props means the bar; `{settings: true}` means the picker; `{provider: "codex" | "claude" | "cursor"}` means details. Use `props`, `theme`, `appHome`, `exec`, `openOverlay`, `closeOverlay`, `shared`, `setShared` and `nextCommand`. Shared key `usage-bar.providers` contains only selected names; `usage-bar.snapshot` contains sanitized usage and errors, never tokens. A new bar clears old snapshots before starting reads. Native `cx.spawn`, a 120000ms timer and callback-owned contexts handle work. String commands refresh/connect-claude/connect-cursor remain supported for optional bindings. There are no global keys or animation.

The mod runs Python 3 with its bundled helper, a provider name and optional `--allow-keychain-prompt` or `--cursor-session-from-clipboard`. Python uses the standard library, Security.framework and CommonCrypto. Each HTTP call has a 10-second timeout, a 1MiB response cap and rejects redirects. Output contains only provider, normalized windows, timestamp, safe error code/message and a next step. Never emit raw responses, cookies, tokens or account identity.

- Codex reads `$CODEX_HOME/auth.json` or `~/.codex/auth.json`. GET `https://chatgpt.com/backend-api/wham/usage` with the saved bearer token and optional ChatGPT-Account-Id. Map primary/secondary rate windows from used_percent/reset_at/limit_window_seconds, labeling actual durations including 30-day plans.
- Claude reads `$CLAUDE_CONFIG_DIR/.credentials.json` or `~/.claude/.credentials.json`, then the exact default-profile Keychain service Claude Code-credentials. Use claudeAiOauth.accessToken, checking expiry and profile scope when supplied. GET `https://api.anthropic.com/api/oauth/usage` with bearer auth and `anthropic-beta: oauth-2025-04-20`; map five_hour/seven_day utilization and resets_at. Do not infer account inactivity from credential failures.
- Cursor first uses an explicitly saved browser session. Otherwise try the CLI auth file (`~/.cursor/auth.json` on macOS, the config home's cursor/auth.json on Linux), macOS CLI Keychain service cursor-access-token/account cursor-user, and the read-only app database's ItemTable cursorAuth/accessToken. On macOS the database is `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb`; on Linux use the config home's Cursor/User/globalStorage/state.vscdb. Read live WAL state when present. Encrypted desktop tokens use exact Keychain service Cursor Safe Storage/account Cursor; decrypt the base64-wrapped v10 AES-CBC payload with a PBKDF2-HMAC-SHA1 key, salt saltysalt, 1003 rounds, 16-byte key, space-filled IV and PKCS7 padding. Validate token expiry and subject. GET `https://cursor.com/api/usage-summary` with `WorkosCursorSessionToken=<subject suffix>%3A%3A<JWT>`. Show individualUsage.plan.totalPercentUsed, or used/limit only when a positive numeric limit exists, and billingCycleEnd.

The copied-session action runs `/usr/bin/pbpaste`, captures its output privately, validates with Cursor before saving, then writes an atomic mode-0600 file at `<HERDR_APP_HOME>/data/usage-bar/cursor-session.json` (default `~/.config/herdr-app`). No credentials go in argv or shared state. No browser-cookie database scanning occurs. Existing provider credentials are never changed or renewed by the mod.

The installer checks the mod, refuses existing destination names, clones the current layout and adds Usage Bar before workspace-status in its 28px row: usage weight 1.35/minimum 300px, original status weight 1. A layout without workspace-status gets a bottom strip. These local layout edits are not packaged layouts. The token SVG is original simple line art; no shipped mod code is copied.

Provider interfaces were checked against [CodexBar's provider documentation](https://github.com/steipete/CodexBar/tree/main/docs) and local Cursor CLI source. The linked [Claude usage mod](https://github.com/dev-gvs/herdr-claude-usage) documents the same credentials-file approach and explicitly notes its lack of macOS Keychain support; it was reviewed as a reference, not installed or copied. CodexBar is not a dependency.

## Watch out

`props()` can be null and `nextCommand()` returns a string. Use the installed generated type files as the native API authority. There is no DOM, Node runtime or JavaScript timeout in a mod. Free legacy Keychain payloads with SecKeychainItemFreeContent. OSStatus -25300 means the requested item is not readable/found, not that a paid account is inactive. HTTP 403 also cannot by itself prove an inactive subscription.

One local account per provider is supported, even while viewing remote terminals. Custom proxies, browser database import, automatic token renewal, API-only quotas, Cursor legacy/team pools, spending and all-time totals are not implemented. Windows is unsupported; Keychain and clipboard connection are macOS-specific. A stored browser session is an explicit override and may need replacing when it expires. Remove `data/usage-bar/cursor-session.json` to forget it and return to automatic source selection. Never include that file in the sharing package.

The native bar, picker toggles, live Codex/Cursor usage, reset countdowns and the connected Cursor popup were visually checked. Claude readings still require a usable sign-in. `herdr-app check` was attempted but timed out initializing macOS window services in the agent sandbox; no passing native check is claimed. Publishing remains deferred until the owner has tested and explicitly requests it.

## Done when

- `herdr-app check ~/.config/herdr-app/mods/usage-bar` passes in a normal local terminal; still pending in the build sandbox.
- Python tests and `node tests/popup-actions.mjs` pass, including private session saving, rejected clipboard values, UI callbacks, preserved readings and hidden-provider polling.
- The token icon opens a picker, toggles update the bar immediately, survive reopening and can hide all providers.
- Refresh stays adjacent to the provider group. Theme changes and narrow allocations remain usable.
- Codex matches its live usage; with usable sign-ins Claude/Cursor show their corresponding windows and resets. Failures display a specific reason and next step without guessing account status.
- The clipboard action validates and privately saves only a usable Cursor session; normal polling never reads the clipboard or prompts Keychain.
- The package contains the mod, brief and real preview, with no layout directory, credentials or full-window capture. Nothing is pushed during local testing.
