# Usage Bar

Codex, Claude and Cursor account usage sits at the left of Herdr's bottom bar. Codex and Claude show the current and weekly quota windows when available; Cursor shows the included plan's billing-cycle total. Percentages mean **used**. A dash means usage could not be read. Clicking a provider shows its reset times or a useful connection error. The preview is a crop of the actual running mod: Codex is connected, while Claude and Cursor still need access to their sign-in data.

![Usage Bar](preview.png)

## What you see

One 28px-high horizontal strip, ordered Codex, Claude, Cursor, then flexible space and a refresh arrow. Each provider is a compact button, with its name in semibold and quota labels such as `5h 52% · 7d 17%` or `Total 35%`. Use the existing UI font at 11.5px. Give the strip 6px horizontal padding, each provider 8px padding (6px below 700px width), and a 4px hover radius. Use theme colors: chrome background, border along the top, foreground names and ordinary numbers, muted labels, dim separators and unavailable values. At 75% used, numbers use the working color; at 95%, the blocked color. Above 760px width, show a dim `quota used` caption before the refresh button. At smaller widths, retain every provider and allow horizontal scrolling.

A provider opens a 440×330px popup with 18px padding: a 16px title and Close button, a plain-language explanation, each available quota with its percentage, a 4px meter and a local-time reset timestamp, then the last successful update time and bottom actions. A failed provider shows its error instead of meters. Claude and Cursor also offer Allow Keychain access. The popup follows the same theme.

## How it behaves

Fetch all three providers independently on first display and every two minutes. The arrow and popup's Refresh all button retry all providers. Never overlap two requests for the same provider. While a first request is pending show an ellipsis; unavailable usage is a dash, never an invented zero. A genuine zero is `0%`; fractional percentages below 1% are `<1%`, and values between 99% and 100% are `>99%`. Values above 100% stay visible; only meter widths clamp at 100%. On refresh failure, discard the provider's previous numbers rather than imply they remain current.

Hover shows the provider's full readings, reset times or error, and explains that clicking opens details. Button controls support their native keyboard behavior. Close or Escape dismisses a popup. There are no added global keybindings, moving elements or animation. Herdr agent states (working, blocked, done, idle) do not alter account quotas or their appearance; the threshold colors describe quota consumption only.

Automatic reads never prompt for Keychain access. Clicking Allow Keychain access retries only that provider with macOS prompting enabled. The person must handle any OS consent dialog. Credentials are read again on later polls, so a provider's own login can renew them. Never refresh, rewrite or export credentials. A background failure in one provider leaves the other two operational.

## Built from

Ship `mods/usage-bar/main.js`, `mod.json` and `collect.py`, this brief, `preview.png`, a README, an installer and parser tests. Do not ship a `layouts/` folder or any account files. No keys.json snippet is needed. The manifest uses `place: "none"` to avoid a second bottom bar, title Usage Bar, size 28, and a 440×330 overlay default.

`main.js` default-exports a `View`, composed of gpui-base horizontal/vertical flex containers and native `Button` controls with gpui-kit divs. Its normal copy has no props. The same mod renders details when passed `{provider: "codex" | "claude" | "cursor"}`; Herdr supplies `overlay` for closing it. Use `props`, `theme`, `appHome`, `exec`, `openOverlay`, `closeOverlay`, `shared`, `setShared`, `nextCommand` and `run`. The main copy keeps sanitized usage in shared key `usage-bar.snapshot` so an open popup updates with it. Handle string commands `refresh`, `connect-claude` and `connect-cursor`. Use `cx.spawn`, a 120000ms data timer and `cx.notify`; never retain a context for later. The mod runs only `python3 <appHome>/mods/usage-bar/collect.py <provider>`, optionally with `--allow-keychain-prompt` after the matching button is clicked.

The Python helper uses only the standard library. Its JSON output contains provider, windows (label, used, reset), update timestamp and a safe error. It never emits credentials or raw HTTP responses. Each HTTP call has a 10-second timeout, a 1MiB response cap and rejects redirects. Do not include emails or account IDs in output. Read only these sources:

- Codex: `$CODEX_HOME/auth.json` or `~/.codex/auth.json`, its `tokens.access_token` and optional `tokens.account_id`. GET `https://chatgpt.com/backend-api/wham/usage` with bearer auth and optional ChatGPT-Account-Id. Map `rate_limit.primary_window` and `secondary_window` using their `used_percent`, `reset_at` and `limit_window_seconds`; name reported durations accurately, including 30-day plans.
- Claude: `$CLAUDE_CONFIG_DIR/.credentials.json` or `~/.claude/.credentials.json`, then the exact macOS Keychain service `Claude Code-credentials` for the default profile only. Read `claudeAiOauth.accessToken`. GET `https://api.anthropic.com/api/oauth/usage` with bearer auth and `anthropic-beta: oauth-2025-04-20`. Map `five_hour.utilization` and `seven_day.utilization`, with their `resets_at` dates.
- Cursor: read `cursorAuth/accessToken` from Cursor's `ItemTable` in its read-only SQLite global state database. On macOS the path is `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb`; on Linux it is under `$XDG_CONFIG_HOME/Cursor/` or `~/.config/Cursor/`. Read the live WAL when present. An absent app token can use `$XDG_CONFIG_HOME/cursor/auth.json` or `~/.config/cursor/auth.json`. An encrypted macOS `cursor-safe-storage:v1:` value is base64-wrapped `v10` AES-CBC ciphertext. Read only Keychain service `Cursor Safe Storage`, account `Cursor`; derive its 16-byte key with PBKDF2-HMAC-SHA1, salt `saltysalt`, 1003 rounds, use a space-filled 16-byte IV and PKCS7 padding through CommonCrypto. Validate the JWT's expiry and subject. GET `https://cursor.com/api/usage-summary` using `WorkosCursorSessionToken=<subject suffix>%3A%3A<token>`. Show `individualUsage.plan.totalPercentUsed`, or compute used/limit only when a positive numeric limit is supplied. Reset at `billingCycleEnd`.

`install.py` first runs the native mod check, copies the mod without overwriting an existing folder, clones the current layout via `layout.clone`, then places the mod before the existing workspace-status block in a non-resizable status row. Give the usage block weight 1.35 and minimum width 300px; the original status block has weight 1. Preserve the existing bar and its commands. For a layout without workspace-status, the installer adds a dedicated bottom strip. These are local layout edits made by the installer; they are not packaged layout files. No shipped mod code or external artwork is required.

Provider shapes were verified against the [Codex](https://github.com/steipete/CodexBar/blob/main/docs/codex.md), [Claude](https://github.com/steipete/CodexBar/blob/main/docs/claude.md) and [Cursor](https://github.com/steipete/CodexBar/blob/main/docs/cursor.md) integration documentation and the upstream [Cursor auth](https://github.com/steipete/CodexBar/blob/main/Sources/CodexBarCore/Providers/Cursor/CursorAppAuth.swift) and [usage types](https://github.com/steipete/CodexBar/blob/main/Sources/CodexBarCore/Providers/Cursor/CursorStatusProbe.swift). Implementation is standalone; CodexBar is not a dependency.

## Watch out

`props()` is null when a layout supplies no props: use optional access. `nextCommand()` returns a string, not an object. Herdr is native GPUI: no HTML, DOM, Node APIs or JavaScript timers in the mod. Use the generated type files from the installed app as the API authority. Keychain freeing uses `SecKeychainItemFreeContent`, not `SecKeychainFreeContent`.

This build supports the signed-in local account for each provider. It does not aggregate accounts or remote machines, parse browser cookies, support custom proxy endpoints, show on-demand spending, handle Cursor legacy request/team pools, or report an all-time total for rolling quotas. An API-only Codex/Claude login or an unlimited/missing Cursor allowance may provide no usable percentage. Claude tokens need usage/profile scope. Provider account endpoints are private interfaces and may change. macOS is required for Keychain and encrypted Cursor support; file-based credentials can work on Linux. Python 3 must be available in Herdr's environment. Shared state persists only normalized usage, not secrets. Reopening a layout starts fresh reads rather than trusting a persisted reading.

The local preview was visually verified with a live Codex reading. Claude and Cursor were not connected during the build and show dashes. The required `herdr-app check` was attempted but timed out while macOS window services were blocked by the agent sandbox; it has **not passed**. Run it in a normal local terminal before treating the build as validated. The installer deliberately stops if that check fails. Public GitHub publishing and topic `herdr-mod` remain deferred until the owner has tested and explicitly requests publication.

## Done when

- `herdr-app check ~/.config/herdr-app/mods/usage-bar` exits successfully. This remains pending in this environment.
- `python3 -m unittest discover -s tests -v` passes the quota parsing and safe-error tests.
- The main copy visibly shows Codex, Claude and Cursor on the left of the bottom bar, with the original status bar still available to its right.
- A signed-in Codex account displays the same current and weekly percentages as its usage page; alternate durations retain their actual labels.
- After granting any needed access, Claude shows the reported 5h and 7d windows and Cursor shows its reported Total, with provider-specific reset times in details. Unavailable readings remain dashes with an explanation.
- Refresh updates the readings; automatic refresh never opens a Keychain dialog. A failure affects only the failed provider.
- Buttons open and close details, hover explains values, theme changes follow Herdr and narrow allocations can scroll the provider row.
- The sharing folder contains the mod, brief and actual preview, with no layout directory, credentials or private full-window capture. Nothing is pushed during local testing.
