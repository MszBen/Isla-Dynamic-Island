"""Audio output hot-plug detection (headphones, headsets, earbuds)."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtMultimedia import QMediaDevices

_HEADPHONE_WORDS = (
    "headphone", "headset", "earphone", "earbud", "buds", "airpods", "hands-free", "handsfree",
    "wh-1000", "wf-1000", "arctis", "hyperx", "corsair void",
)


def is_headphones(name: str) -> bool:
    n = name.lower()
    return any(w in n for w in _HEADPHONE_WORDS)


class AudioWatcher(QObject):
    added = Signal(str, bool)  # name, looks_like_headphones
    removed = Signal(str, bool)

    def __init__(self) -> None:
        super().__init__()
        self._media = QMediaDevices(self)
        self._known = self._snapshot()
        self._media.audioOutputsChanged.connect(self._changed)

    def _snapshot(self) -> dict[bytes, str]:
        return {bytes(d.id()): d.description() for d in QMediaDevices.audioOutputs()}

    def _changed(self) -> None:
        now = self._snapshot()
        for key, name in now.items():
            if key not in self._known:
                self.added.emit(name, is_headphones(name))
        for key, name in self._known.items():
            if key not in now and is_headphones(name):
                self.removed.emit(name, True)
        self._known = now
