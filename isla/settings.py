"""Standalone settings window (a normal window, separate from the island), styled like Isla."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from . import hooks_install
from .agents import AgentHub
from .config import Config
from .mascot import Mascot
from .system import autostart_enabled, set_autostart

STYLE = """
QWidget#root { background: #0C0B12; }
QWidget { color: #F2F0FA; font-family: 'Segoe UI'; font-size: 10pt; }
QLabel#title { font-size: 20pt; font-weight: 700; }
QLabel#subtitle, QLabel#hint, QLabel#value { color: #8E8AA3; }
QLabel#section { color: #8E8AA3; font-size: 8pt; font-weight: 600; letter-spacing: 1px; }
QLabel#status { font-weight: 600; }
QFrame#card { background: rgba(255,255,255,0.05); border-radius: 18px; }
QFrame#divider { background: rgba(255,255,255,0.07); max-height: 1px; border: none; }
QPushButton {
    background: rgba(255,255,255,0.09); border: none; border-radius: 14px; padding: 0 16px; min-height: 28px;
}
QPushButton:hover { background: rgba(255,255,255,0.15); }
QPushButton:disabled { color: rgba(242,240,250,0.3); background: rgba(255,255,255,0.04); }
QPushButton#primary { background: #B9A7FF; color: #0C0B12; font-weight: 600; }
QPushButton#primary:hover { background: #CABCFF; }
QPushButton#primary:disabled { background: rgba(185,167,255,0.25); color: rgba(12,11,18,0.5); }
QSlider::groove:horizontal { height: 6px; border-radius: 3px; background: rgba(255,255,255,0.14); }
QSlider::sub-page:horizontal { border-radius: 3px; background: #B9A7FF; }
QSlider::handle:horizontal {
    width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; background: #F2F0FA;
}
"""


class Switch(QCheckBox):
    """iOS-style toggle in Isla's accent colour."""

    def __init__(self) -> None:
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(44, 24)
        self._pos = 0.0
        self._anim = QVariantAnimation(self, duration=140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._set_pos)
        self.toggled.connect(self._slide)

    def _set_pos(self, v) -> None:
        self._pos = float(v)
        self.update()

    def _slide(self, on: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def setChecked(self, on: bool) -> None:  # jump without animating when set programmatically
        super().setChecked(on)
        self._anim.stop()
        self._set_pos(1.0 if on else 0.0)

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        track = QColor("#B9A7FF") if self.isChecked() else QColor(255, 255, 255, 40)
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(0, 0, 44, 24), 12, 12)
        p.setBrush(QColor("#0C0B12") if self.isChecked() else QColor("#F2F0FA"))
        p.drawEllipse(QRectF(3 + 20 * self._pos, 3, 18, 18))


def _label(text: str, name: str = "") -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    return lab


class Card(QFrame):
    """Rounded panel holding rows separated by hairlines."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("card")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(18, 6, 18, 6)
        self._lay.setSpacing(0)
        self._rows = 0

    def row(self, title: str, control: QWidget | None = None, hint: str = "") -> None:
        if self._rows:
            line = QFrame()
            line.setObjectName("divider")
            self._lay.addWidget(line)
        self._rows += 1
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 12, 0, 12)
        text = QVBoxLayout()
        text.setSpacing(1)
        text.addWidget(_label(title))
        if hint:
            text.addWidget(_label(hint, "hint"))
        h.addLayout(text, 1)
        if control is not None:
            h.addWidget(control, 0, Qt.AlignVCenter)
        self._lay.addWidget(box)


class SettingsWindow(QWidget):
    def __init__(self, cfg: Config, hub: AgentHub, on_focus_change=None):
        super().__init__()
        self.cfg, self.hub = cfg, hub
        self._on_focus_change = on_focus_change
        self.setObjectName("root")
        self.setWindowTitle("Isla Settings")
        self.setMinimumWidth(480)
        self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 24)
        root.setSpacing(8)

        # header: mascot + title
        head = QHBoxLayout()
        face = QLabel()
        pm = QPixmap(112, 112)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        Mascot().paint(p, QRectF(0, 0, 112, 112))
        p.end()
        pm.setDevicePixelRatio(2)
        face.setPixmap(pm)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(_label("Isla", "title"))
        titles.addWidget(_label("Settings", "subtitle"))
        head.addWidget(face)
        head.addSpacing(6)
        head.addLayout(titles, 1)
        root.addLayout(head)
        root.addSpacing(8)

        # general
        root.addWidget(_label("GENERAL", "section"))
        self.autostart = Switch()
        self.autostart.setChecked(autostart_enabled())
        self.autostart.toggled.connect(self._on_autostart)
        card = Card()
        card.row("Start with Windows", self.autostart, "Launch Isla when you sign in")
        root.addWidget(card)
        root.addSpacing(6)

        # island
        root.addWidget(_label("ISLAND", "section"))
        self.fullscreen = Switch()
        self.fullscreen.setChecked(cfg.hide_in_fullscreen)
        self.fullscreen.toggled.connect(lambda v: self._set("hide_in_fullscreen", v))
        self.peeks = Switch()
        self.peeks.setChecked(cfg.status_peeks)
        self.peeks.toggled.connect(lambda v: self._set("status_peeks", v))
        self.confetti = Switch()
        self.confetti.setChecked(cfg.confetti)
        self.confetti.toggled.connect(lambda v: self._set("confetti", v))
        self.lyrics = Switch()
        self.lyrics.setChecked(cfg.lyrics_enabled)
        self.lyrics.toggled.connect(lambda v: self._set("lyrics_enabled", v))
        self.collapse, self._collapse_val = self._slider(100, 2000, cfg.collapse_delay_ms, "{} ms", "collapse_delay_ms", 50)
        self.ghost, self._ghost_val = self._slider(5, 60, round(cfg.ghost_opacity * 100), "{}%", "ghost_opacity", 1, 0.01)
        card = Card()
        card.row("Hide in fullscreen", self.fullscreen, "Step aside for games and videos")
        card.row("Status peeks", self.peeks, "Charger and headphones animations")
        card.row("Confetti", self.confetti, "When Claude or a focus session finishes")
        card.row("Synced lyrics", self.lyrics, "Fetched from LRCLIB")
        card.row("Collapse delay", self._with_value(self.collapse, self._collapse_val), "After the mouse leaves")
        card.row("Ghost opacity", self._with_value(self.ghost, self._ghost_val), "After a double-click")
        root.addWidget(card)
        root.addSpacing(6)

        # focus
        root.addWidget(_label("FOCUS TIMER", "section"))
        self.chime = Switch()
        self.chime.setChecked(cfg.focus_chime)
        self.chime.toggled.connect(lambda v: self._set("focus_chime", v))
        self.f_work, self._f_work_val = self._slider(5, 90, cfg.focus_work_min, "{} min", "focus_work_min", 5)
        self.f_short, self._f_short_val = self._slider(1, 30, cfg.focus_short_min, "{} min", "focus_short_min", 1)
        self.f_long, self._f_long_val = self._slider(5, 60, cfg.focus_long_min, "{} min", "focus_long_min", 5)
        card = Card()
        card.row("Focus length", self._with_value(self.f_work, self._f_work_val), "Pomodoro work session")
        card.row("Short break", self._with_value(self.f_short, self._f_short_val))
        card.row("Long break", self._with_value(self.f_long, self._f_long_val), "After every 4 sessions")
        card.row("Chime", self.chime, "Plays when a phase ends")
        root.addWidget(card)
        root.addSpacing(6)

        # agents
        root.addWidget(_label("CLAUDE CODE", "section"))
        self.hook_status = _label("", "status")
        self.install = QPushButton("Install")
        self.install.setObjectName("primary")
        self.remove = QPushButton("Remove")
        self.install.clicked.connect(lambda: self._hooks(True))
        self.remove.clicked.connect(lambda: self._hooks(False))
        buttons = QWidget()
        bl = QHBoxLayout(buttons)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.addWidget(self.hook_status)
        bl.addSpacing(6)
        bl.addWidget(self.remove)
        bl.addWidget(self.install)
        self.timeout, self._timeout_val = self._slider(10, 120, int(cfg.approval_timeout_s), "{} s", "approval_timeout_s", 5)
        self.timeout.valueChanged.connect(lambda v: setattr(self.hub, "approval_timeout", v))
        card = Card()
        card.row("Hooks", buttons, "Shows agent activity and approvals")
        card.row("Approval wait", self._with_value(self.timeout, self._timeout_val), "Then Claude Code asks in the terminal")
        root.addWidget(card)
        self._refresh_hooks()

    # -- helpers -------------------------------------------------------
    def _slider(self, lo: int, hi: int, value: int, fmt: str, name: str, step: int, scale: float = 1.0):
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi)
        s.setSingleStep(step)
        s.setPageStep(step)
        s.setValue(value)
        s.setFixedWidth(150)
        lab = _label(fmt.format(value), "value")
        lab.setFixedWidth(52)
        lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        def changed(v: int) -> None:
            v = round(v / step) * step if step > 1 else v
            lab.setText(fmt.format(v))
            self._set(name, round(v * scale, 2) if scale != 1.0 else v)

        s.valueChanged.connect(changed)
        return s, lab

    @staticmethod
    def _with_value(slider: QSlider, label: QLabel) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(slider)
        h.addWidget(label)
        return w

    # -- handlers ------------------------------------------------------
    def _set(self, name: str, value) -> None:
        setattr(self.cfg, name, value)
        self.cfg.save()
        if name.startswith("focus_") and self._on_focus_change:
            self._on_focus_change()

    def _on_autostart(self, on: bool) -> None:
        try:
            set_autostart(on)
        except OSError:
            self.autostart.blockSignals(True)
            self.autostart.setChecked(autostart_enabled())
            self.autostart.blockSignals(False)

    def _hooks(self, install: bool) -> None:
        try:
            hooks_install.install() if install else hooks_install.uninstall()
        except (OSError, ValueError):
            self.hook_status.setText("Failed")
            return
        self._refresh_hooks()

    def _refresh_hooks(self) -> None:
        on = hooks_install.is_installed()
        self.hook_status.setText("● Connected" if on else "○ Not installed")
        self.hook_status.setStyleSheet("color: #5FD38D;" if on else "color: #8E8AA3;")
        self.install.setEnabled(not on)
        self.remove.setEnabled(on)

    def showEvent(self, e) -> None:
        self._refresh_hooks()
        self.autostart.blockSignals(True)
        self.autostart.setChecked(autostart_enabled())
        self.autostart.blockSignals(False)
        for slider, label, value in (  # lengths can also change from the island
            (self.f_work, self._f_work_val, self.cfg.focus_work_min),
            (self.f_short, self._f_short_val, self.cfg.focus_short_min),
            (self.f_long, self._f_long_val, self.cfg.focus_long_min),
        ):
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
            label.setText(f"{value} min")
        super().showEvent(e)
