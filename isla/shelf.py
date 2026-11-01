"""File shelf store: remembers paths (not copies) across restarts."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ShelfItem:
    path: str

    @property
    def name(self) -> str:
        return Path(self.path).name or self.path

    @property
    def exists(self) -> bool:
        return os.path.exists(self.path)

    @property
    def size_text(self) -> str:
        p = Path(self.path)
        if p.is_dir():
            return "Folder"
        try:
            n = float(p.stat().st_size)
        except OSError:
            return "Missing"
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024 or unit == "GB":
                return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
            n /= 1024
        return ""


class Shelf:
    def __init__(self, store: Path):
        self._store = store
        self.items: list[ShelfItem] = []
        self._load()

    def _load(self) -> None:
        try:
            paths = json.loads(self._store.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            paths = []
        self.items = [ShelfItem(p) for p in paths if isinstance(p, str) and os.path.exists(p)]

    def _save(self) -> None:
        self._store.write_text(json.dumps([i.path for i in self.items]), encoding="utf-8")

    def add(self, paths: list[str]) -> int:
        have = {i.path for i in self.items}
        added = 0
        for p in paths:
            p = os.path.normpath(p)
            if p not in have and os.path.exists(p):
                self.items.append(ShelfItem(p))
                have.add(p)
                added += 1
        if added:
            self._save()
        return added

    def remove(self, path: str) -> None:
        self.items = [i for i in self.items if i.path != path]
        self._save()
