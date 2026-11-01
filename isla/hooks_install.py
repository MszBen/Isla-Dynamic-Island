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
MARKERS = ("isla_hook.py", "isla-hook.exe")  # script when run from source, small exe when packaged
MARKER = MARKERS[0]
HOOK_SCRIPT = Path(__file__).resolve().parent.parent / "hooks" / MARKER
SETTINGS = Path.home() / ".claude" / "settings.json"


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def packaged_hook_exe() -> Path:
    """The relay as a standalone exe folder (bundled inside Isla.exe), copied next to Isla's data.

    Claude Code runs it on every tool call, so it must start fast and not need Python installed.
    """
    from .config import data_dir

    src = Path(getattr(sys, "_MEIPASS", ".")) / "isla-hook"  # a folder: starts ~6x faster than a one-file exe
    dst = data_dir() / "isla-hook"
    exe = dst / "isla-hook.exe"
    if (src / "isla-hook.exe").exists() and (
        not exe.exists() or exe.stat().st_size != (src / "isla-hook.exe").stat().st_size
    ):
        shutil.copytree(src, dst, dirs_exist_ok=True)
    return exe


def hook_command() -> str:
    # Forward slashes: Claude Code runs hook commands through a POSIX shell on Windows.
    if frozen():
        return f'"{packaged_hook_exe().as_posix()}"'
    return f'"{Path(sys.executable).as_posix()}" "{HOOK_SCRIPT.as_posix()}"'


def _is_ours(entry: dict) -> bool:
    return any(m in h.get("command", "") for h in entry.get("hooks", []) for m in MARKERS)


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
