"""Clipboard history: newest first, de-duplicated, searchable. Kept in memory only (clips can hold secrets)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

MAX_CLIPS = 100
MAX_LEN = 20_000


@dataclass(frozen=True)
class Clip:
    text: str
    when: float = field(default_factory=time.time)

    @property
    def preview(self) -> str:
        """One line for the list: whitespace collapsed."""
        return " ".join(self.text.split())


class ClipHistory:
    def __init__(self, limit: int = MAX_CLIPS):
        self.limit = limit
        self.clips: list[Clip] = []  # newest first
        self.hidden: set[str] = set()  # forgotten here; stays out when Windows' own history is merged in again

    def add(self, text: str) -> bool:
        text = text[:MAX_LEN]
        if not text.strip():
            return False
        self.hidden.discard(text)
        self.clips = [c for c in self.clips if c.text != text]  # re-copying moves it back to the top
        self.clips.insert(0, Clip(text))
        del self.clips[self.limit:]
        return True

    def search(self, query: str) -> list[Clip]:
        """Every whitespace-separated word must appear somewhere in the clip (case-insensitive)."""
        words = query.lower().split()
        return [c for c in self.clips if all(w in c.text.lower() for w in words)]

    def merge(self, entries: list[tuple[str, float]]) -> bool:
        """Folds in (text, time) pairs from Windows' clipboard history; ours win on duplicates. True if anything new."""
        have = {c.text for c in self.clips}
        new = [Clip(t[:MAX_LEN], w) for t, w in entries if t.strip() and t[:MAX_LEN] not in have and t not in self.hidden]
        if not new:
            return False
        seen: set[str] = set()
        merged = []
        for c in sorted(self.clips + new, key=lambda c: c.when, reverse=True):
            if c.text not in seen:
                seen.add(c.text)
                merged.append(c)
        self.clips = merged[:self.limit]
        return True

    def remove(self, text: str) -> None:
        self.hidden.add(text)
        self.clips = [c for c in self.clips if c.text != text]

    def clear(self) -> None:
        self.hidden.update(c.text for c in self.clips)
        self.clips = []


def age_text(seconds: float) -> str:
    if seconds < 60:
        return "now"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h"
    return f"{int(seconds // 86400)}d"
