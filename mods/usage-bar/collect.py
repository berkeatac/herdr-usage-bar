#!/usr/bin/env python3
"""Read-only account quotas. stdout contains normalized usage, never credentials."""
import argparse
import base64
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import sqlite3
import sys
import time
import urllib.error
import urllib.request


class Unavailable(Exception):
    pass


def number(value):
    return (float(value) if isinstance(value, (int, float))
            and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None)


def window(label, percent, reset=None):
    n = number(percent)
    return {"label": label, "used": n, "reset": reset} if n is not None else None


def load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        raise Unavailable("Cannot read sign-in data; sign in again in the provider app.")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a bearer token/cookie to a redirected destination.
        raise Unavailable("Usage endpoint redirected; provider integration needs an update.")


def request(url, headers):
    req = urllib.request.Request(url, headers={"User-Agent": "HerdrUsageBar/1.0", **headers})
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=10) as response:
            result = json.loads(response.read(1024 * 1024))
            if not isinstance(result, dict):
                raise Unavailable("Unexpected usage response; provider integration needs an update.")
            return result
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise Unavailable("Sign in again in the provider app; usage access was rejected.")
        if e.code == 429:
            raise Unavailable("Rate limited; wait a few minutes before refreshing.")
        raise Unavailable("Provider returned HTTP " + str(e.code) + ".")
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError):
        raise Unavailable("Cannot reach provider; check your connection.")
    except (ValueError, UnicodeError):
        raise Unavailable("Unexpected usage response; provider integration needs an update.")


def keychain(service, account=None, allow_prompt=False):
    """Read one exact macOS generic-password item. No browser/keychain scanning."""
    if sys.platform != "darwin":
        return None
    sec = ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")
    sec.SecKeychainSetUserInteractionAllowed.argtypes = [ctypes.c_bool]
    sec.SecKeychainSetUserInteractionAllowed(allow_prompt)
    sec.SecKeychainFindGenericPassword.argtypes = [ctypes.c_void_p, ctypes.c_uint32,
        ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    sec.SecKeychainItemFreeContent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    service_b = service.encode()
    account_b = account.encode() if account else None
    size, data = ctypes.c_uint32(), ctypes.c_void_p()
    status = sec.SecKeychainFindGenericPassword(None, len(service_b), service_b,
        len(account_b) if account_b else 0, account_b, ctypes.byref(size), ctypes.byref(data), None)
    if status != 0:
        return None
    try:
        return ctypes.string_at(data, size.value).decode("utf-8")
    finally:
        sec.SecKeychainItemFreeContent(None, data)


def decrypt_cursor(value, allow_prompt=False):
    if not value.startswith("cursor-safe-storage:"):
        return value
    if not value.startswith("cursor-safe-storage:v1:"):
        raise Unavailable("Unsupported Cursor credential format.")
    secret = keychain("Cursor Safe Storage", "Cursor", allow_prompt)
    if not secret:
        raise Unavailable("Keychain access needed. Click Cursor, then Allow Keychain access.")
    payload = base64.b64decode(value.split(":", 2)[2], validate=True)
    if payload[:3] != b"v10" or not payload[3:] or len(payload[3:]) % 16:
        raise Unavailable("Unsupported Cursor encrypted credential.")
    key = hashlib.pbkdf2_hmac("sha1", secret.encode(), b"saltysalt", 1003, 16)
    crypto = ctypes.CDLL("/usr/lib/system/libcommonCrypto.dylib")
    crypto.CCCrypt.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
        ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    output = ctypes.create_string_buffer(len(payload))
    count = ctypes.c_size_t()
    status = crypto.CCCrypt(1, 0, 1, key, len(key), b" " * 16,
        payload[3:], len(payload) - 3, output, len(output), ctypes.byref(count))
    if status:
        raise Unavailable("Could not unlock Cursor sign-in data; sign in again in Cursor.")
    return output.raw[:count.value].decode("utf-8")


def parse_codex(data):
    rate = data.get("rate_limit") or {}
    windows = []
    for key, fallback in (("primary_window", "Current"), ("secondary_window", "7d")):
        item = rate.get(key) or {}
        seconds = number(item.get("limit_window_seconds"))
        label = ("7d" if seconds == 604800 else "5h" if seconds == 18000 else
                 str(int(seconds / 3600)) + "h" if seconds and seconds < 86400 else
                 str(int(seconds / 86400)) + "d" if seconds else fallback)
        w = window(label, item.get("used_percent"), item.get("reset_at"))
        if w:
            windows.append(w)
    return windows


def codex(allow_prompt=False):
    root = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    tokens = load_json(root / "auth.json").get("tokens") or {}
    token = tokens.get("access_token")
    if not token:
        raise Unavailable("Sign in with codex login. API-key accounts have no subscription quota here.")
    headers = {"Authorization": "Bearer " + token}
    if tokens.get("account_id"):
        headers["ChatGPT-Account-Id"] = tokens["account_id"]
    return parse_codex(request("https://chatgpt.com/backend-api/wham/usage", headers))


def parse_claude(data):
    result = []
    for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
        item = data.get(key) or {}
        w = window(label, item.get("utilization"), item.get("resets_at"))
        if w:
            result.append(w)
    return result


def claude(allow_prompt=False):
    root = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    credentials = load_json(root / ".credentials.json")
    if not credentials.get("claudeAiOauth") and "CLAUDE_CONFIG_DIR" not in os.environ:
        raw = keychain("Claude Code-credentials", allow_prompt=allow_prompt)
        if raw:
            credentials = json.loads(raw)
    token = (credentials.get("claudeAiOauth") or {}).get("accessToken")
    if not token:
        raise Unavailable("Claude Code sign-in or Keychain access needed. Open details to connect.")
    return parse_claude(request("https://api.anthropic.com/api/oauth/usage",
        {"Authorization": "Bearer " + token, "anthropic-beta": "oauth-2025-04-20"}))


def cursor_token(allow_prompt=False):
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    db = (Path.home() / "Library/Application Support/Cursor/User/globalStorage/state.vscdb"
          if sys.platform == "darwin" else config / "Cursor/User/globalStorage/state.vscdb")
    token = None
    if db.exists():
        # Read the live WAL when present; immutable only for a quiescent database.
        suffix = "?mode=ro" if Path(str(db) + "-wal").exists() else "?mode=ro&immutable=1"
        with sqlite3.connect(db.as_uri() + suffix, uri=True, timeout=1) as connection:
            row = connection.execute("SELECT value FROM ItemTable WHERE key=? LIMIT 1",
                                     ("cursorAuth/accessToken",)).fetchone()
        if row:
            token = row[0]
            if isinstance(token, bytes):
                token = token.decode("utf-16-le" if b"\x00" in token else "utf-8")
    if not token:
        token = load_json(config / "cursor/auth.json").get("accessToken")
    if not token:
        raise Unavailable("Sign in to Cursor or run cursor-agent login.")
    token = decrypt_cursor(token, allow_prompt)
    try:
        part = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        if float(claims.get("exp", 0)) <= time.time() + 60:
            raise Unavailable("Cursor sign-in expired; open Cursor and sign in again.")
        user = claims["sub"].split("|")[-1]
        if not user or any(not (c.isascii() and (c.isalnum() or c in "._-")) for c in user):
            raise ValueError()
    except (KeyError, IndexError, ValueError, TypeError):
        raise Unavailable("Invalid Cursor sign-in data; sign in again in Cursor.")
    return user + "%3A%3A" + token


def parse_cursor(data):
    plan = (data.get("individualUsage") or {}).get("plan") or {}
    if plan.get("enabled") is False:
        return []
    percent = number(plan.get("totalPercentUsed"))
    if percent is None:
        used, limit = number(plan.get("used")), number(plan.get("limit"))
        if used is not None and limit is not None and limit > 0:
            percent = used / limit * 100
    w = window("Total", percent, data.get("billingCycleEnd"))
    return [w] if w else []


def cursor(allow_prompt=False):
    return parse_cursor(request("https://cursor.com/api/usage-summary",
        {"Cookie": "WorkosCursorSessionToken=" + cursor_token(allow_prompt)}))


def collect(provider, allow_prompt=False):
    try:
        windows = {"codex": codex, "claude": claude, "cursor": cursor}[provider](allow_prompt)
        if not windows:
            raise Unavailable("Provider did not report a supported quota. No usage percentage is assumed.")
        return {"provider": provider, "windows": windows, "updated": int(time.time()), "error": None}
    except Unavailable as e:
        return {"provider": provider, "windows": [], "updated": None, "error": str(e)}
    except Exception:
        # Never echo exceptions containing request URLs, headers or credential values.
        return {"provider": provider, "windows": [], "updated": None,
                "error": "Could not read usage; check provider sign-in and local file permissions."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=["codex", "claude", "cursor"])
    parser.add_argument("--allow-keychain-prompt", action="store_true")
    args = parser.parse_args()
    print(json.dumps(collect(args.provider, args.allow_keychain_prompt), allow_nan=False))
