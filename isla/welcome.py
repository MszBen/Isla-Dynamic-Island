"""First-run quick tour (also reachable from the tray menu, island menu and settings)."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import hooks_install
from .mascot import Mascot
from .settings import STYLE, Card, _label

TIPS = [
    ("Hover over the island", "It expands into Music, Focus timer, File shelf and Claude Code tabs."),
    ("Drop files onto it", "Keep them on the shelf, then drag them out into any app later."),
    ("Double-click to see through", "Isla fades out and clicks pass through until you move your mouse away."),
    ("Right-click for the menu", "Settings, this tour and Quit live there (and on the tray icon)."),
    ("Poke the mascot", "It reacts to music, timers and Claude Code. Poke it a few times and see."),
]


class WelcomeWindow(QWidget):
    def __init__(self, on_settings=None) -> None:
        super().__init__()
        self._on_settings = on_settings
        self.setObjectName("root")
        self.setWindowTitle("Welcome to Isla")
        self.setMinimumWidth(500)
        self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 24)
        root.setSpacing(10)

        head = QHBoxLayout()
        face = QLabel()
        pm = QPixmap(112, 112)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        m = Mascot()
        m.paint(p, QRectF(0, 0, 112, 112))
        p.end()
        pm.setDevicePixelRatio(2)
        face.setPixmap(pm)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(_label("Welcome to Isla", "title"))
        titles.addWidget(_label("A little island at the top of your screen. Here's how it works.", "subtitle", wrap=True))
        head.addWidget(face)
        head.addSpacing(6)
        head.addLayout(titles, 1)
        root.addLayout(head)
        root.addSpacing(4)

        card = Card()
        for title, hint in TIPS:
            card.row(title, None, hint)
        root.addWidget(card)

        self.connect_status = _label("", "hint", wrap=True)
        card = Card()
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._connect)
        card.row("Using Claude Code?", self.connect_btn,
                 "Follow what it's doing and approve actions right from the island.")
        root.addWidget(card)
        root.addWidget(self.connect_status)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        settings = QPushButton("Open settings")
        settings.clicked.connect(self._open_settings)
        done = QPushButton("Got it")
        done.setObjectName("primary")
        done.clicked.connect(self.close)
        buttons.addWidget(settings)
        buttons.addWidget(done)
        root.addLayout(buttons)
        self._refresh()

    def _refresh(self) -> None:
        on = hooks_install.is_installed()
        self.connect_btn.setEnabled(not on)
        self.connect_btn.setText("Connected ✓" if on else "Connect")

    def _connect(self) -> None:
        try:
            hooks_install.install()
            self.connect_status.setText("Connected. Restart any Claude Code sessions that are already open.")
        except (OSError, ValueError):
            self.connect_status.setText("Couldn't update Claude Code's settings file. You can retry in Settings.")
        self._refresh()

    def _open_settings(self) -> None:
        self.close()
        if self._on_settings:
            self._on_settings()

    def showEvent(self, e) -> None:
        self._refresh()
        super().showEvent(e)
