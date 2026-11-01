"""Wires services to the island and adds a tray icon."""
from __future__ import annotations

import sys

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .agents import AgentHub
from .config import Config, data_dir
from .island import Island
from .mascot import Mascot
from .media import MediaService
from .settings import SettingsWindow
from .shelf import Shelf


def _tray_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    m = Mascot()
    m.paint(p, QRectF(0, 0, 64, 64))
    p.end()
    return QIcon(pm)


def run() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Isla")

    cfg = Config.load()
    base = data_dir()
    media = MediaService()
    hub = AgentHub(cfg.port, cfg.approval_timeout_s)
    shelf = Shelf(base / "shelf.json")
    island = Island(cfg, media, hub, shelf, base / "lyrics")

    if not hub.start():
        print(f"[isla] port {cfg.port} busy; agent hooks disabled", file=sys.stderr)
    media.start()
    island.show()

    tray = QSystemTrayIcon(_tray_icon(), app)
    menu = QMenu()
    settings = SettingsWindow(cfg, hub)

    def open_settings() -> None:
        settings.show()
        settings.raise_()
        settings.activateWindow()

    open_ = QAction("Settings…", menu)
    open_.triggered.connect(open_settings)
    tray.activated.connect(lambda r: open_settings() if r == QSystemTrayIcon.Trigger else None)
    quit_ = QAction("Quit Isla", menu)
    quit_.triggered.connect(app.quit)
    menu.addAction(open_)
    menu.addSeparator()
    menu.addAction(quit_)
    tray.setContextMenu(menu)
    tray.setToolTip("Isla")
    tray.show()

    app.aboutToQuit.connect(hub.stop)
    return app.exec()
