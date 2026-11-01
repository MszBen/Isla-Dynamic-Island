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


_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_NAME = "Isla"


def _autostart_command() -> str:
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent.as_posix()
    exe = Path(sys.executable.replace("python.exe", "pythonw.exe")).as_posix()
    code = f"import sys; sys.path.insert(0, r'{root}'); from isla.__main__ import main; main()"
    return f'"{exe}" -c "{code}"'


def autostart_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            winreg.QueryValueEx(k, _RUN_NAME)
        return True
    except OSError:
        return False


def set_autostart(on: bool) -> None:
    if sys.platform != "win32":
        return
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, _RUN_NAME, 0, winreg.REG_SZ, _autostart_command())
        else:
            try:
                winreg.DeleteValue(k, _RUN_NAME)
            except OSError:
                pass
