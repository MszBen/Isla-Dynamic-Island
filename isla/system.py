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


def set_click_through(hwnd: int, on: bool) -> None:
    """Toggle WS_EX_TRANSPARENT so mouse input falls through the window to whatever is below."""
    if sys.platform != "win32":
        return
    GWL_EXSTYLE, WS_EX_TRANSPARENT, WS_EX_LAYERED = -20, 0x20, 0x80000
    user32 = ctypes.windll.user32
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style = (style | WS_EX_TRANSPARENT | WS_EX_LAYERED) if on else (style & ~WS_EX_TRANSPARENT)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
