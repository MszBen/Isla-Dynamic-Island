"""Small Windows helpers."""
from __future__ import annotations

import ctypes
import sys


def fullscreen_app_active() -> bool:
    """True when a fullscreen app/game/presentation is in front (Nusa-style 'step aside')."""
    if sys.platform != "win32":
        return False
    state = ctypes.c_int(0)
    try:
        ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state))
    except Exception:
        return False
    # 2 = QUNS_BUSY (fullscreen), 3 = D3D fullscreen, 4 = presentation mode
    return state.value in (2, 3, 4)
