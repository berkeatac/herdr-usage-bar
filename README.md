# Usage Bar for Herdr

Codex, Claude and Cursor subscription usage on the left of your bottom bar.

![Usage Bar showing Codex current and weekly usage alongside Cursor Auto and other models](preview.png)

## Features

- **Choose providers:** click the token icon to show or hide Codex, Claude and Cursor. Your choices are saved; hidden providers stop polling.
- **Usage at a glance:** current and weekly windows for Codex and Claude, and Cursor’s Auto and other-model usage for the billing cycle. Percentages show quota **used**.
- **Optional countdowns:** each provider popup has a **Show countdowns in bar** checkbox. Enable or remove countdowns independently for each provider. Codex/Claude default on; Cursor defaults off.
- **Reset details:** see remaining time such as `2h 15m` or `3d 12h`, plus the exact reset timestamp in the popup. Countdowns update every minute without extra API calls.
- **Codex credits:** the Codex popup shows remaining additional usage credits, including zero, unlimited credits and unavailable balances, separately from rolling plan limits.
- **Local sign-ins and Keychain:** reuse existing provider credentials, with an explicit **Retry Keychain** action for Claude and Cursor on macOS. Connected providers hide their connection controls.
- **Cursor browser connection:** explicitly connect using a copied browser session if Keychain is unavailable.
- **Refresh:** the refresh arrow stays next to the provider displays. Automatic refresh runs every two minutes; popups also offer **Refresh all**.
- **Useful errors:** click `!` for the reason and a next step, including missing login, expired credentials, denied access or unsupported quotas.

The screenshot shows the selected Codex and Cursor providers; Claude can be enabled from the token icon.

## Install with your agent

With Herdr running, paste this into your coding agent:

```text
Read ~/.config/herdr-app/AGENTS.md, then install the Usage Bar mod from
https://github.com/berkeatac/herdr-usage-bar.
Read its RECIPE.md and all mod files first. Explain its network, program
and local credential access before installing. Preserve my existing mods,
keys and layout. Add the bar to the left of the bottom status bar in a
personal copy of my current layout, following Herdr's clone instructions.
Run herdr-app check on the mod. Do not copy RECIPE.md or preview.png into
Herdr's config folder, and never overwrite an existing mod.
```

This repository ships a **mod**, with no `layouts/` folder and no required `keys.json` snippet. A mod needs a block in your own layout to appear in the bottom bar.

## Install from a terminal

Requires Herdr, Python 3 and Git. Keep Herdr running and run these commands from a normal local terminal:

```sh
git clone https://github.com/berkeatac/herdr-usage-bar.git
cd herdr-usage-bar
python3 install.py
```

The installer validates the mod, refuses existing destination names, copies `mods/usage-bar/` into Herdr’s mod directory and uses `layout.clone` to make a personal copy of your active layout. It adds Usage Bar to the left of the existing status display. Layouts without the standard status bar get a bottom strip. The clone is named `<current-layout>-usage`; it becomes active. Your original layout remains available through **Ctrl+Shift+L**.

For manual installation, copy only `mods/usage-bar/` to `~/.config/herdr-app/mods/`, run `herdr-app check ~/.config/herdr-app/mods/usage-bar`, then add a block with `"content": { "mod": "usage-bar" }` at the left of a 28px bottom row in a layout you own. Clone shipped layouts before editing. If `usage-bar` already exists, stop and resolve the name collision rather than overwriting it.

## Connect providers

**Codex:** uses the existing CLI login in `$CODEX_HOME/auth.json` or `~/.codex/auth.json`. Run `codex login` if necessary. API-key accounts do not provide subscription quota here.

**Claude:** uses its credentials file or macOS Keychain login. Run `claude` and sign in if no subscription login exists. **Retry Keychain** can request access to a saved login; granting access does not create a login or activate a plan.

**Cursor:** tries its independent CLI login before desktop-token decryption. Run `cursor-agent login` if needed, or use **Retry Keychain** in the popup. If Keychain remains unavailable:

1. In a signed-in `cursor.com` tab, open browser DevTools → Application → Cookies.
2. Copy only the `WorkosCursorSessionToken` value.
3. Click **Cursor → Use copied browser session** in the mod. Do not paste the token into chat.

This button reads the clipboard only when clicked, validates the session with Cursor, and saves an owner-only file at `~/.config/herdr-app/data/usage-bar/cursor-session.json` (or under `HERDR_APP_HOME`). Automatic refresh uses that session without Keychain. Replace it through the same button if it expires. Delete that file to forget the override and return to automatic source selection. No browser cookie database is scanned.

## Data access and limitations

The mod runs its bundled Python helper, reads known provider credential sources outside its own folder, and requests usage from `chatgpt.com`, `api.anthropic.com` and `cursor.com`. Existing provider credentials are never changed or renewed. Only the explicit copied-session action saves a new local credential. Ordinary polling never reads the clipboard or prompts Keychain.

Normalized readings and preferences are stored in Herdr shared state. Secrets never go into shared state, command arguments, logs or this repository. macOS supports Keychain and clipboard connection; Linux supports file-based sign-ins. Windows, multiple accounts per provider, API-key billing and Cursor team/legacy pools are unsupported. Provider endpoints can change.

## Validation and rebuilding

```sh
python3 -m unittest discover -s tests -v
node tests/popup-actions.mjs
node --check mods/usage-bar/main.js
herdr-app check ~/.config/herdr-app/mods/usage-bar
```

Python and popup callback tests pass with synthetic credentials. The native check remains pending: it timed out initializing macOS window services in the build sandbox. The running bar, picker, live Codex/Cursor usage and reset details were visually checked; the new credits row has automated coverage but still needs a native visual check. Claude needs a usable sign-in to verify live readings.

[RECIPE.md](RECIPE.md) is the full brief for rebuilding from an empty folder. The installation guide follows the agent-first approach of [herdr-claude-usage](https://github.com/dev-gvs/herdr-claude-usage); its code is not a dependency.
