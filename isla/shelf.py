"""File shelf store: remembers paths (not copies) across restarts."""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ShelfItem:
    path: str
    group: str = ""  # items added together share a group id; "" = on its own

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
            raw = json.loads(self._store.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = []
        items = []
        for entry in raw if isinstance(raw, list) else []:
            # older files are a plain list of paths; newer ones hold {"path", "group"}
            path, group = (entry, "") if isinstance(entry, str) else (
                (entry.get("path"), entry.get("group", "")) if isinstance(entry, dict) else (None, ""))
            if isinstance(path, str) and isinstance(group, str) and os.path.exists(path):
                items.append(ShelfItem(path, group))
        self.items = items

    def _save(self) -> None:
        data = [{"path": i.path, "group": i.group} if i.group else i.path for i in self.items]
        self._store.write_text(json.dumps(data), encoding="utf-8")

    def add(self, paths: list[str]) -> int:
        """Adds files; several added at once become one group."""
        have = {i.path for i in self.items}
        new: list[str] = []
        for p in paths:
            p = os.path.normpath(p)
            if p not in have and os.path.exists(p):
                new.append(p)
                have.add(p)
        group = uuid.uuid4().hex[:8] if len(new) > 1 else ""
        self.items.extend(ShelfItem(p, group) for p in new)
        if new:
            self._save()
        return len(new)

    def blocks(self) -> list[list[ShelfItem]]:
        """Display order: newest first, members of a group kept together (a lone survivor is not a group)."""
        out: list[list[ShelfItem]] = []
        for item in self.items:
            if out and item.group and out[-1][0].group == item.group:
                out[-1].append(item)
            else:
                out.append([item])
        out.reverse()
        return out

    def ordered(self) -> list[ShelfItem]:
        return [i for block in self.blocks() for i in block]

    def clear(self) -> None:
        self.items = []
        self._save()

    def remove(self, path: str) -> None:
        self.items = [i for i in self.items if i.path != path]
        self._save()
