"""Real mouse clicks on the settings window (no registry / settings-file side effects)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from isla import settings as settings_mod
from isla.agents import AgentHub
from isla.config import Config


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(qapp, monkeypatch):
    monkeypatch.setattr(settings_mod, "set_autostart", lambda on: None)
    monkeypatch.setattr(settings_mod, "autostart_enabled", lambda: False)
    monkeypatch.setattr(settings_mod.hooks_install, "is_installed", lambda *a, **k: False)
    calls = []
    monkeypatch.setattr(settings_mod.hooks_install, "install", lambda *a, **k: calls.append("install"))
    cfg = Config()
    cfg.save = lambda *a, **k: None
    w = settings_mod.SettingsWindow(cfg, AgentHub(0), lambda: calls.append("focus"))
    w.calls = calls
    w.show()
    qapp.processEvents()
    yield w
    w.close()


def click(widget, x=None):
    pos = widget.rect().center() if x is None else QPoint(int(widget.width() * x), widget.rect().center().y())
    QTest.mouseClick(widget, Qt.LeftButton, Qt.NoModifier, pos)


@pytest.mark.parametrize("attr,field", [
    ("fullscreen", "hide_in_fullscreen"), ("peeks", "status_peeks"), ("confetti", "confetti"),
    ("lyrics", "lyrics_enabled"), ("chime", "focus_chime"),
])
def test_clicking_a_toggle_flips_the_setting(win, attr, field):
    sw = getattr(win, attr)
    before = getattr(win.cfg, field)
    click(sw)                                   # anywhere on the switch, not just its left edge
    assert sw.isChecked() is (not before)
    assert getattr(win.cfg, field) is (not before)
    click(sw, 0.9)                              # and the right-hand side works too
    assert getattr(win.cfg, field) is before


def test_start_with_windows_toggle(win, monkeypatch):
    seen = []
    monkeypatch.setattr(settings_mod, "set_autostart", seen.append)
    click(win.autostart)
    assert seen == [True]


@pytest.mark.parametrize("attr,field", [
    ("collapse", "collapse_delay_ms"), ("ghost", "ghost_opacity"), ("f_work", "focus_work_min"),
    ("f_short", "focus_short_min"), ("f_long", "focus_long_min"), ("timeout", "approval_timeout_s"),
])
def test_clicking_a_slider_changes_the_setting(win, attr, field):
    before = getattr(win.cfg, field)
    click(getattr(win, attr), 0.05)             # near the left end: always a different value
    assert getattr(win.cfg, field) != before


def test_focus_sliders_notify_the_island(win):
    click(win.f_work, 0.9)
    assert "focus" in win.calls


def test_connect_and_footer_buttons(win):
    buttons = {b.text(): b for b in win.findChildren(QPushButton)}
    click(buttons["Connect"])
    assert "install" in win.calls
    fired = []
    win.on_tour, win.on_quit = lambda: fired.append("tour"), lambda: fired.append("quit")
    click(buttons["Quick tour"])
    click(buttons["Quit Isla"])
    assert fired == ["tour", "quit"]
