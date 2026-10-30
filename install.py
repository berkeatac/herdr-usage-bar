#!/usr/bin/env python3
"""Install Usage Bar into a personal copy of the current layout; never publish."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
NAME = "usage-bar"


def add_usage(node):
    """Insert the mod to the left of a stock status bar, preserving that bar."""
    content = node.get("content", {})
    if node.get("type") == "block" and content.get("mod") == "workspace-status":
        old = dict(node)
        old["id"] = str(node["id"]) + "-original"
        old.pop("size", None)
        old["size"] = {"weight": 1}
        node.pop("content")
        node["type"] = "row"
        node["resizable"] = False
        node["children"] = [
            {"id": "usage-bar", "type": "block", "size": {"weight": 1.35},
             "min": 300, "content": {"mod": NAME}}, old]
        return True
    return any(add_usage(child) for child in node.get("children", []))


def command(*args):
    r = subprocess.run(["herdr-app", *args], capture_output=True, text=True, timeout=25)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout).strip())
    return r.stdout


def main():
    home = Path(os.environ.get("HERDR_APP_HOME", Path.home() / ".config/herdr-app"))
    destination = home / "mods" / NAME
    if destination.exists():
        raise RuntimeError(f"{destination} exists. Refusing to overwrite; keep or move your existing mod first.")
    state = json.loads((home / "shared.json").read_text())
    original = state.get("layout", "main")
    clone = original + "-usage"
    if (home / "layouts" / (clone + ".json")).exists():
        raise RuntimeError(f"Layout {clone} already exists; refusing to overwrite.")
    tree = json.loads((home / "layouts" / (original + ".json")).read_text())
    inserted = add_usage(tree)
    if not inserted:
        # A layout without the standard status bar gets a dedicated bottom strip.
        tree = {"id": "usage-root", "type": "column", "children": [tree,
                {"id": NAME, "type": "block", "size": {"px": 28}, "content": {"mod": NAME}}]}
    # Validate source first; no layout is changed after a failed native check.
    print(command("check", str(ROOT / "mods" / NAME)).strip())
    shutil.copytree(ROOT / "mods" / NAME, destination,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.error",
                                                  "gpui-kit.d.ts", "herdr.d.ts", "jsconfig.json"))
    command("do", "layout.clone", json.dumps({"name": original, "as": clone}))
    path = home / "layouts" / (clone + ".json")
    clone_tree = json.loads(path.read_text())
    if inserted:
        add_usage(clone_tree)
    else:
        tree["children"][0] = clone_tree
        # Window and appearance properties belong to the new root.
        for key in ("titlebar", "traffic_lights", "theme", "colors", "font", "font_size",
                    "ui_font", "terminal_padding", "terminal_opacity", "terminal_menu"):
            if key in clone_tree:
                tree[key] = clone_tree.pop(key)
        clone_tree = tree
    path.write_text(json.dumps(clone_tree, indent=2) + "\n")
    print(f"Installed in personal layout {clone}. Switch back with Ctrl+Shift+L.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as e:
        sys.exit(f"Install stopped: {e}")
