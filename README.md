# Usage Bar for Herdr

Codex, Claude and Cursor subscription usage on the left of your bottom bar.

![Usage Bar](preview.png)

Click the **token icon** to choose providers. Your choices are saved; hidden providers stop polling. The refresh arrow stays beside the displays. Percentages show **used** quota: current/weekly windows for Codex and Claude, Cursor's included billing-cycle Total. `!` means unavailable; click for the reason and next step.

## Connecting providers

Codex uses its existing CLI login. Claude uses its credentials file or Keychain login; **Retry Keychain** cannot create a login or activate a plan. Run `claude` and sign in if no subscription login exists. Errors distinguish missing login, expiry, denied access, missing scope, API rejection and plans without a supported quota. The mod does not guess whether a subscription is inactive.

Cursor tries its independent CLI login before desktop-token decryption. Run `cursor-agent login` if needed. If Keychain remains unavailable, click **Cursor → Use copied browser session**:

1. In a signed-in `cursor.com` tab, open browser DevTools → Application → Cookies.
2. Copy only the `WorkosCursorSessionToken` value.
3. Click **Use copied browser session** in the mod. Do not paste the token into chat.

This explicit button reads the clipboard, validates the session with Cursor, and saves an owner-only file at `~/.config/herdr-app/data/usage-bar/cursor-session.json` (or under HERDR_APP_HOME). Automatic refresh uses that session without Keychain. Replace it through the same button if it expires. Delete that file to forget it and return to automatic source selection. No browser cookie database is scanned.

## Local testing and installation

The installed mod is `~/.config/herdr-app/mods/usage-bar`. It is placed in a personal copy of the standard layout, currently `main-copy`. No global keybindings are added. The package is a mod, contains no `layouts/` folder and has not been published.

On another setup, with Herdr and Python 3 installed:

```sh
python3 install.py
```

The installer first validates the mod, refuses destination collisions, clones the current layout and adds the bar while preserving the original status bar. For manual placement use a `{ "mod": "usage-bar" }` block at the left of a 28px status row in a layout you own.

## Data access and checks

The helper reads only known provider auth sources and calls `chatgpt.com`, `api.anthropic.com` and `cursor.com` for usage. Saved provider credentials are not changed or refreshed. Normalized readings and provider preferences are kept in Herdr shared state; secrets never go there, into command arguments, logs or this repository. Only the explicit copied-session action saves a new local credential. macOS supports Keychain and clipboard connection; Linux supports file-based sign-ins. Windows is unsupported.

```sh
python3 -m unittest discover -s tests -v
node tests/popup-actions.mjs
node --check mods/usage-bar/main.js
herdr-app check ~/.config/herdr-app/mods/usage-bar
```

The native check is still pending because the build sandbox cannot initialize macOS window services. The actual bar, provider picker and connection panels were visually verified, including live Codex data; live Cursor/Claude readings need usable sign-ins. Tests use synthetic credentials and never read the user's clipboard.

See [RECIPE.md](RECIPE.md) for the complete rebuilding brief and limits. The reference [Claude usage mod](https://github.com/dev-gvs/herdr-claude-usage) also notes that its credentials-file method does not read macOS Keychain; installing it would not fix a missing Mac login.

Nothing is pushed. After the owner's testing and explicit publication request, publish the package to a public GitHub repository with topic `herdr-mod`. Never include `data/`, credentials or full-window screenshots.
