# Usage Bar for Herdr

Codex, Claude and Cursor subscription usage at the left of the bottom bar. Percentages show **used** quota: current and weekly windows where available, or Cursor's included billing-cycle **Total**.

![Usage Bar](preview.png)

This is a local test build. Nothing has been published. The preview is a cropped screenshot of the real running bar; Claude and Cursor show dashes until connected.

## Test the installed copy

The local mod is installed at `~/.config/herdr-app/mods/usage-bar`. The personal layout `main-usage` places it beside the original status bar. Choose **Layout: Main-usage** in Herdr's command palette if another layout is selected. Click a provider for reset times or an error; click the arrow to refresh. Claude and Cursor's **Allow Keychain access** button asks macOS for permission to read their existing sign-in item. Automatic refresh does not prompt. Sign in through the provider's own app if a token has expired.

No global keys are added. The bar refreshes every two minutes. A missing reading is a dash, never an assumed zero. It reads the local signed-in accounts even when viewing a remote space.

Run the required native check from your ordinary Mac terminal:

```sh
herdr-app check ~/.config/herdr-app/mods/usage-bar
```

The build session could not complete that check because macOS window services were blocked in its sandbox. Native rendering, a live Codex reading and the details popup were visually verified. Claude/Cursor live readings still need Keychain access and testing.

## Install on another setup

Requires Herdr and Python 3. On macOS, the helper can use native Keychain and decrypt current Cursor app credentials. Linux supports file-based sign-in sources; Windows is not supported.

```sh
python3 install.py
```

The installer validates the source mod, refuses existing destination names, clones the current layout and adds the bar to that personal copy. It preserves the original status bar. The package intentionally has no `layouts/` folder and needs no keys.json snippet. For a custom installation, put a `{ "mod": "usage-bar" }` block on the left of your own 28px status row.

## Data access

The mod runs its bundled Python helper. It reads Codex/Claude sign-in files, Cursor's read-only state database or CLI auth file, and these exact macOS Keychain items when accessible: **Claude Code-credentials** and **Cursor Safe Storage / Cursor**. It contacts only `chatgpt.com`, `api.anthropic.com` and `cursor.com` for usage. Tokens stay in memory and go only to their own provider; no credential is printed, copied into this repository, or changed. The mod stores normalized readings in Herdr shared state. It does not read browser cookies, launch model requests or install dependencies.

These provider account interfaces can change. API-key-only accounts, Cursor legacy/team quotas and multiple accounts are outside this build. See [RECIPE.md](RECIPE.md) for the complete rebuilding brief and endpoint sources.

## Validation and removal

```sh
python3 -m unittest discover -s tests -v
node --check mods/usage-bar/main.js
herdr-app check mods/usage-bar
```

Switch back to the original layout before removing the mod and its personal layout copy. Do not delete the shipped main layout. Local full-window screenshots are ignored under `.local/`; `preview.png` contains only the usage strip.

When the owner approves publication, publish this folder to a public GitHub repository and set topic `herdr-mod`. Do not publish until that approval arrives.
