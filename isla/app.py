"""Wires services to the island and adds a tray icon."""
from __future__ import annotations

import logging
import sys
import threading

from PySide6.QtCore import QLockFile, QRectF, Qt
from PySide6.QtGui import QAction, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from .agents import AgentHub
from .config import Config, data_dir
from .devices import AudioWatcher
from .island import Island
from .mascot import Mascot
from .media import AVAILABLE as MEDIA_OK
from .media import MediaService
from .power import PowerMonitor
from .settings import SettingsWindow
from .shelf import Shelf
from .welcome import WelcomeWindow

# Dark menus and tooltips so the island's context menu and hints match its look.
APP_STYLE = """
QToolTip { background: #1C1A26; color: #F2F0FA; border: 1px solid #3A3550; padding: 4px 8px; font-family: 'Segoe UI'; }
QMenu { background: #14121C; color: #F2F0FA; border: 1px solid #2E2A40; border-radius: 10px; padding: 6px; font-family: 'Segoe UI'; }
QMenu::item { padding: 7px 22px 7px 14px; border-radius: 6px; }
QMenu::item:selected { background: rgba(185,167,255,0.22); }
QMenu::separator { height: 1px; background: rgba(255,255,255,0.08); margin: 5px 8px; }
"""


def _tray_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    m = Mascot()
    m.paint(p, QRectF(0, 0, 64, 64))
    p.end()
    return QIcon(pm)


def _setup_logging(base) -> None:
    """Windowless runs (Isla.pyw) have no console, so write problems to a log file."""
    logging.basicConfig(filename=str(base / "isla.log"), level=logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")

    def hook(kind, value, tb) -> None:
        logging.error("Unhandled exception", exc_info=(kind, value, tb))

    sys.excepthook = hook
    threading.excepthook = lambda a: hook(a.exc_type, a.exc_value, a.exc_traceback)


def run() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Isla")
    app.setStyleSheet(APP_STYLE)

    cfg = Config.load()
    base = data_dir()
    _setup_logging(base)

    lock = QLockFile(str(base / "isla.lock"))  # keep a reference for the app's lifetime
    if not lock.tryLock(200):
        QMessageBox.information(
            None, "Isla", "Isla is already running.\n\nLook for the island at the top of your screen, "
                          "or the Isla icon near your clock (it may be under the ^ arrow).")
        return 0

    media = MediaService()
    hub = AgentHub(cfg.port, cfg.approval_timeout_s)
    shelf = Shelf(base / "shelf.json")
    island = Island(cfg, media, hub, shelf, base / "lyrics")

    hooks_ok = hub.start()
    media.start()
    if not MEDIA_OK:
        logging.warning("Windows media controls are unavailable; the Music tab will stay empty")

    power = PowerMonitor()
    power.changed.connect(
        lambda plugged, pct: island.show_peek(
            "charging" if plugged else "battery",
            "Charging" if plugged else "On battery",
            "Charger connected" if plugged else "Charger unplugged",
            pct,
        )
    )
    power.start()
    audio = AudioWatcher()
    audio.added.connect(
        lambda name, hp: island.show_peek("headphones", "Headphones connected" if hp else "Audio device connected", name)
    )
    audio.removed.connect(lambda name, _hp: island.show_peek("headphones_off", "Headphones disconnected", name))
    island.show()

    tray = QSystemTrayIcon(_tray_icon(), app)
    menu = QMenu()
    settings = SettingsWindow(cfg, hub, island.apply_focus_config)
    settings.on_display = island.apply_display
    settings.shown_changed.connect(island.set_settings_open)

    def bring_to_front(w) -> None:
        w.show()
        w.raise_()
        w.activateWindow()

    def open_settings() -> None:
        bring_to_front(settings)

    tour = WelcomeWindow(open_settings)

    def open_tour() -> None:
        bring_to_front(tour)

    settings.on_tour, settings.on_quit = open_tour, app.quit
    island.open_settings.connect(open_settings)
    island.open_tour.connect(open_tour)
    island.quit_requested.connect(app.quit)

    open_ = QAction("Settings…", menu)
    open_.triggered.connect(open_settings)
    tour_ = QAction("Quick tour", menu)
    tour_.triggered.connect(open_tour)
    quit_ = QAction("Quit Isla", menu)
    quit_.triggered.connect(app.quit)
    menu.addAction(open_)
    menu.addAction(tour_)
    menu.addSeparator()
    menu.addAction(quit_)
    tray.setContextMenu(menu)
    tray.setToolTip("Isla: click for settings, right-click for more")
    tray.activated.connect(lambda r: open_settings() if r == QSystemTrayIcon.Trigger else None)
    tray.show()

    if not hooks_ok:
        tray.showMessage("Isla", f"Couldn't start the Claude Code listener (port {cfg.port} is busy). "
                                 "Everything else still works.", QSystemTrayIcon.Warning, 8000)
    if not cfg.welcomed:  # first run: explain how Isla works
        cfg.welcomed = True
        cfg.save()
        open_tour()

    app.aboutToQuit.connect(hub.stop)
    code = app.exec()
    lock.unlock()
    return code
