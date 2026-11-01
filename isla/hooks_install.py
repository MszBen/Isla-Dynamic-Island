"""Safely merge Isla's hooks into Claude Code's settings.json (idempotent, backed up)."""
from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path

EVENTS = [
    "SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse",
    "Notification", "PermissionRequest", "Stop", "SessionEnd",
]
MARKER = "isla_hook.py"
HOOK_SCRIPT = Path(__file__).resolve().parent.parent / "hooks" / MARKER
SETTINGS = Path.home() / ".claude" / "settings.json"


def hook_command() -> str:
    # Forward slashes: Claude Code runs hook commands through a POSIX shell on Windows.
    return f'"{Path(sys.executable).as_posix()}" "{HOOK_SCRIPT.as_posix()}"'


def _is_ours(entry: dict) -> bool:
    return any(MARKER in h.get("command", "") for h in entry.get("hooks", []))


def merge(settings: dict, command: str) -> dict:
    out = copy.deepcopy(settings)
    hooks = out.setdefault("hooks", {})
    for event in EVENTS:
        entries = [e for e in hooks.get(event, []) if not _is_ours(e)]
        timeout = 130 if event == "PermissionRequest" else 10
        entries.append({"matcher": "", "hooks": [{"type": "command", "command": command, "timeout": timeout}]})
        hooks[event] = entries
    return out


def remove(settings: dict) -> dict:
    out = copy.deepcopy(settings)
    hooks = out.get("hooks", {})
    for event in list(hooks):
        hooks[event] = [e for e in hooks[event] if not _is_ours(e)]
        if not hooks[event]:
            del hooks[event]
    if not hooks:
        out.pop("hooks", None)
    return out


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def install(path: Path = SETTINGS, dry_run: bool = False) -> str:
    current = _load(path)
    new = merge(current, hook_command())
    text = json.dumps(new, indent=2)
    if dry_run:
        return text
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_suffix(".json.isla-backup"))
    path.write_text(text, encoding="utf-8")
    return f"Hooks installed in {path} (backup: {path.name}.isla-backup)"


def uninstall(path: Path = SETTINGS) -> str:
    if not path.exists():
        return "Nothing to remove."
    shutil.copy2(path, path.with_suffix(".json.isla-backup"))
    path.write_text(json.dumps(remove(_load(path)), indent=2), encoding="utf-8")
    return f"Isla hooks removed from {path}"


def is_installed(path: Path = SETTINGS) -> bool:
    try:
        hooks = _load(path).get("hooks", {})
    except (OSError, ValueError):
        return False
    return any(_is_ours(e) for entries in hooks.values() for e in entries)
