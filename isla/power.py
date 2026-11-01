"""Charger plug/unplug detection via GetSystemPowerStatus."""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import QObject, QTimer, Signal


class _Status(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_ubyte),
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),
        ("SystemStatusFlag", ctypes.c_ubyte),
        ("BatteryLifeTime", wintypes.DWORD),
        ("BatteryFullLifeTime", wintypes.DWORD),
    ]


def interpret(ac: int, flag: int, percent: int) -> tuple[bool, int] | None:
    """(plugged_in, battery_percent), or None when there is no battery / unknown state."""
    if flag == 128 or ac == 255 or percent == 255:
        return None
    return ac == 1, percent


def read() -> tuple[bool, int] | None:
    if sys.platform != "win32":
        return None
    st = _Status()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(st)):
        return None
    return interpret(st.ACLineStatus, st.BatteryFlag, st.BatteryLifePercent)


class PowerMonitor(QObject):
    changed = Signal(bool, int)  # plugged_in, percent (emitted on plug/unplug only)

    def __init__(self) -> None:
        super().__init__()
        cur = read()
        self._plugged = cur[0] if cur else None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        self._timer.start(2000)

    def _poll(self) -> None:
        cur = read()
        if cur is None:
            return
        if self._plugged is not None and cur[0] != self._plugged:
            self.changed.emit(*cur)
        self._plugged = cur[0]
