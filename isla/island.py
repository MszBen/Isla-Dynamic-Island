"""The island window: one frameless widget whose size morphs between modes.

Modes: compact (idle pill) | expanded (tabs: music / shelf / agents) | approval | toast.
Everything is painted by hand; clickable regions are collected into self._hits while painting.
"""
from __future__ import annotations

import math
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve, QFileInfo, QMimeData, QPointF, QRectF, QSizeF, Qt, QTimer, QUrl,
    QPropertyAnimation, QVariantAnimation, Signal,
)
from PySide6.QtGui import (
    QColor, QCursor, QDrag, QFont, QFontMetrics, QGuiApplication, QPainter, QLinearGradient, QPainterPath, QPen,
    QPixmap, QPolygonF,
)
from PySide6.QtWidgets import QFileIconProvider, QWidget

from .agents import AgentHub, Approval
from .config import Config
from .lyrics import Line, current_index, fetch_lyrics
from .mascot import BODY, Mascot
from .media import MediaInfo, MediaService
from .focus import LABEL, LONG, SHORT, WORK, FocusTimer, format_clock
from .shelf import Shelf
from .sound import play_chime
from .system import fullscreen_app_active, set_click_through

BG = QColor("#0C0B12")
TEXT = QColor("#F2F0FA")
DIM = QColor("#8E8AA3")
ACCENT = QColor("#B9A7FF")
CLAUDE = QColor("#D97757")
CLAUDE_INK = QColor("#2A150C")
CLAUDE_DARK = QColor("#1C120E")
CLAUDE_PEACH = QColor("#FFE3D3")
GREEN = QColor("#5FD38D")
AMBER = QColor("#FFC857")
RED = QColor("#FF6B6B")
FONT = "Segoe UI"

SIZES = {"expanded": (500, 248), "approval": (470, 132), "toast": (330, 44), "peek": (350, 58)}
TABS = ("Music", "Focus", "Shelf", "Agents")
STATUS_COLOR = {"idle": DIM, "working": ACCENT, "waiting": AMBER, "done": GREEN}


def fmt_minutes(seconds: float) -> str:
    return "<1 min" if seconds < 60 else f"{int(seconds // 60)} min"


def fmt_tokens(n: int) -> str:
    if n < 1000:
        return str(n)
    return f"{n / 1000:.1f}k" if n < 1_000_000 else f"{n / 1_000_000:.2f}M"


def fmt_time(s: float) -> str:
    s = max(0, int(s))
    return f"{s // 60}:{s % 60:02d}"


class Island(QWidget):
    lyrics_ready = Signal(object, object)  # (artist, title), list[Line]

    def __init__(self, cfg: Config, media: MediaService, hub: AgentHub, shelf: Shelf, cache_dir: Path):
        super().__init__()
        self.cfg, self.media_svc, self.hub, self.shelf = cfg, media, hub, shelf
        self.cache_dir = cache_dir
        self.mascot = Mascot()
        self.focus = FocusTimer()
        self.apply_focus_config()

        self.media = MediaInfo()
        self._media_stamp = time.monotonic()
        self._art: QPixmap | None = None
        self.lines: list[Line] = []
        self._lines_key: tuple[str, str] | None = None
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="isla-lyrics")

        self.approvals: list[Approval] = []
        self._claude = None  # Session while Claude is working
        self.accent = ACCENT
        self._toast: tuple[str, str] | None = None
        self._peek: tuple[str, str, str, int, float] | None = None  # kind, title, subtitle, percent, start
        self.tab = "Music"
        self._hover = False
        self._dropping = False
        self._dragging_out = False
        self._ghost = False
        self._press_arg = None
        self._press: tuple[QPointF, str] | None = None
        self._last_active = time.monotonic()
        self._hits: list[tuple[QRectF, str, object]] = []
        self._icons: dict[str, QPixmap] = {}
        self._icon_provider = QFileIconProvider()

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAcceptDrops(True)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(340)
        self._anim.setEasingCurve(QEasingCurve.OutBack)
        self._anim.valueChanged.connect(self._on_size)
        self._size = QSizeF(*self._target_size())
        self._target = self._size
        self._place(self._size)

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(180)

        self._frame = QTimer(self)
        self._frame.timeout.connect(self._tick)
        self._collapse = QTimer(self, singleShot=True)
        self._collapse.timeout.connect(self._end_hover)
        self._expand = QTimer(self, singleShot=True)
        self._expand.timeout.connect(self._begin_hover)
        self._ghost_poll = QTimer(self)  # watches the cursor while click-through (no mouse events arrive)
        self._ghost_poll.timeout.connect(self._check_ghost)
        self._slow = QTimer(self)  # 1 Hz housekeeping: mood, fullscreen, clock
        self._slow.timeout.connect(self._housekeeping)
        self._slow.start(1000)

        self.lyrics_ready.connect(self._on_lyrics)
        media.changed.connect(self._on_media)
        hub.sessions_changed.connect(self._on_agents)
        hub.approval_requested.connect(self._on_approval)
        hub.approval_finished.connect(self._on_approval_done)
        hub.attention.connect(self._on_attention)

    # ------------------------------------------------------------------ mode
    @property
    def mode(self) -> str:
        if self.approvals:
            return "approval"
        if self._hover or self._dropping:
            return "expanded"
        if self._peek:
            return "peek"
        if self._toast:
            return "toast"
        return "compact"

    def apply_focus_config(self) -> None:
        c = self.cfg
        self.focus.configure(c.focus_work_min * 60, c.focus_short_min * 60, c.focus_long_min * 60, c.focus_cycles)
        self.update()

    def _focus_tick(self) -> None:
        for event in self.focus.tick(time.monotonic()):
            if self.cfg.focus_chime:
                play_chime(self.cache_dir.parent)
            if event == "break":
                self.show_peek("focus", "Time for a break", f"{self.cfg.focus_short_min} min · well done", seconds=4)
            elif event == "long_break":
                self.show_peek("focus", "Long break", f"{self.cfg.focus_long_min} min · session complete", seconds=4)
            elif event == "work_resume":
                self.show_peek("focus", "Back to focus", f"{format_clock(self.focus.remaining)} left", seconds=3)
            else:
                self.show_peek("focus", "Break's over", "Ready when you are", seconds=4)

    def _focus_adjust(self, delta: float) -> None:
        """Change the current phase's length from the island and remember it in the settings."""
        f = self.focus
        if not f.adjust(delta):
            return
        field = {WORK: "focus_work_min", SHORT: "focus_short_min", LONG: "focus_long_min"}[f.phase]
        setattr(self.cfg, field, round({WORK: f.work, SHORT: f.short, LONG: f.long}[f.phase] / 60))
        self.cfg.save()
        self.update()

    def wheelEvent(self, e) -> None:
        if self.mode == "expanded" and self.tab == "Focus":
            self._focus_adjust(60.0 if e.angleDelta().y() > 0 else -60.0)

    def _focus_text(self) -> str:
        f = self.focus
        text = f"{f.label} · {format_clock(f.remaining)}"
        return text if f.running else text + " · paused"

    def _compact_text(self) -> str:
        if self._claude:
            s = self._claude
            parts = ["Claude", fmt_minutes(s.elapsed)]
            if s.tokens is not None:
                parts.append(f"{fmt_tokens(s.tokens)} tokens")
            return " · ".join(parts)
        if self.focus.active:
            return self._focus_text()
        m = self.media
        if m.active and m.playing:
            i = current_index(self.lines, self._position())
            if i >= 0 and self.lines[i].text:
                return self.lines[i].text
            return f"{m.title} — {m.artist}" if m.artist else m.title
        return time.strftime("%H:%M")

    def _target_size(self) -> tuple[float, float]:
        mode = self.mode
        if mode == "compact":
            fm = QFontMetrics(QFont(FONT, 10))
            w = 36 + 30 + fm.horizontalAdvance(self._compact_text()) + 44
            return (max(170.0, min(float(w), 400.0)), 38.0)
        return SIZES[mode]

    def _apply_mode(self) -> None:
        if self._ghost:  # frozen in place so the cursor can leave the area it was over
            return
        w, h = self._target_size()
        if abs(w - self._target.width()) < 1 and abs(h - self._target.height()) < 1:
            self.update()
            return
        self._target = QSizeF(w, h)
        self._anim.stop()
        self._anim.setStartValue(self._size)
        self._anim.setEndValue(self._target)
        self._anim.start()
        self._kick()

    def _on_size(self, v) -> None:
        self._size = QSizeF(v)
        self._place(self._size)

    def _place(self, size: QSizeF) -> None:
        scr = QGuiApplication.primaryScreen().geometry()
        w, h = max(int(size.width()), 60), max(int(size.height()), 30)
        self.setGeometry(scr.x() + (scr.width() - w) // 2, scr.y() + 8, w, h)

    # ----------------------------------------------------------------- timers
    def _kick(self) -> None:
        if not self._frame.isActive():
            self._frame.start(33)

    def _tick(self) -> None:
        self.mascot.update()
        busy = (
            self._anim.state() == QVariantAnimation.Running
            or self.mascot.animating
            or self._peek is not None
            or self._claude is not None
            or (self.media.active and self.media.playing and self.mode in ("expanded", "compact"))
        )
        self.update()
        if not busy:
            self._frame.stop()
        else:
            self._frame.setInterval(33 if self._anim.state() == QVariantAnimation.Running else 66)

    def _housekeeping(self) -> None:
        if self.cfg.hide_in_fullscreen and not self.approvals:
            if fullscreen_app_active():
                self.hide()
            elif not self.isVisible():
                self.show()
        self._focus_tick()
        self.hub.refresh_tokens()
        self._refresh_claude()
        self._refresh_mood()
        if self.mode == "compact":
            self._apply_mode()  # clock / lyric line may have changed the width
            self.update()

    def _refresh_claude(self) -> None:
        """Claude working takes priority over music: orange theme + run stats."""
        s = self.hub.active_session()
        was = self._claude is not None
        self._claude = s
        self.accent = CLAUDE if s else ACCENT
        self.mascot.body = CLAUDE_PEACH if s else BODY
        if s and not was:
            self.tab = "Agents"
        if bool(s) != was:
            self._apply_mode()
            self._kick()
        self.update()

    def _refresh_mood(self) -> None:
        sessions = self.hub.snapshot()
        if self.approvals or any(s.status == "waiting" for s in sessions):
            rest = "curious"
        elif any(s.status == "working" for s in sessions):
            rest = "focused"
        elif self.focus.running and self.focus.phase == WORK:
            rest = "focused"
        elif self.media.active and self.media.playing:
            rest = "music"
        elif time.monotonic() - self._last_active > 120:
            rest = "sleepy"
        else:
            rest = "idle"
        self.mascot.set_rest(rest)
        if rest != "idle":
            self._kick()

    # ---------------------------------------------------------------- signals
    def _position(self) -> float:
        m = self.media
        if m.playing:
            p = m.position + (time.monotonic() - self._media_stamp)
            return min(p, m.duration) if m.duration > 0 else p
        return m.position

    def _on_media(self, info: MediaInfo) -> None:
        changed = info.key != self.media.key
        self.media, self._media_stamp = info, time.monotonic()
        if changed:
            self.lines, self._lines_key = [], None
            self._art = None
            if info.art:
                pm = QPixmap()
                if pm.loadFromData(info.art):
                    self._art = pm
            if info.active and info.title and self.cfg.lyrics_enabled:
                key, dur = info.key, info.duration
                self._pool.submit(
                    lambda: self.lyrics_ready.emit(key, fetch_lyrics(key[0], key[1], dur, self.cache_dir))
                )
        self._refresh_mood()
        self._apply_mode()
        self.update()

    def _on_lyrics(self, key, lines) -> None:
        if key == self.media.key:
            self.lines, self._lines_key = lines, key
            self._apply_mode()
            self.update()

    def _on_agents(self) -> None:
        self._refresh_claude()
        self._refresh_mood()
        self.update()

    def _on_approval(self, ap: Approval) -> None:
        self.approvals.append(ap)
        self._refresh_claude()
        self.mascot.flash("curious", 6)
        if not self.isVisible():
            self.show()
        self._apply_mode()
        self._kick()

    def _on_approval_done(self, approval_id: str) -> None:
        self.approvals = [a for a in self.approvals if a.id != approval_id]
        self._apply_mode()
        self._refresh_mood()

    def _on_attention(self, kind: str, text: str) -> None:
        self.mascot.flash("happy" if kind == "done" else "curious", 4)
        self._toast = (kind, text)
        QTimer.singleShot(4000, self._clear_toast)
        self._apply_mode()
        self._kick()

    def show_peek(self, kind: str, title: str, subtitle: str = "", percent: int = 0, seconds: float = 3.4) -> None:
        """Brief status animation: kind is 'charging' | 'battery' | 'headphones' | 'headphones_off'."""
        if not self.cfg.status_peeks:
            return
        peek = (kind, title, subtitle, percent, time.monotonic())
        self._peek = peek
        self.mascot.flash("love" if kind == "headphones" else "happy", seconds)
        QTimer.singleShot(int(seconds * 1000), lambda: self._clear_peek(peek))
        self._apply_mode()
        self._kick()

    def _clear_peek(self, peek) -> None:
        if self._peek is peek:
            self._peek = None
            self._apply_mode()

    def _clear_toast(self) -> None:
        self._toast = None
        self._apply_mode()

    # ------------------------------------------------------------ hover / drag
    def enterEvent(self, e) -> None:
        self._collapse.stop()
        self._last_active = time.monotonic()
        if self.mascot.emotion == "sleepy":
            self.mascot.flash("wink", 1.5)
        if not self._hover:
            self._expand.start(120)

    def leaveEvent(self, e) -> None:
        self._expand.stop()
        if not self._dragging_out:
            self._collapse.start(self.cfg.collapse_delay_ms)

    def _begin_hover(self) -> None:
        self._hover = True
        self._apply_mode()

    def _end_hover(self) -> None:
        self._hover = self._dropping = False
        self._apply_mode()

    def dragEnterEvent(self, e) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._collapse.stop()
            self._dropping, self.tab = True, "Shelf"
            self._apply_mode()

    def dragLeaveEvent(self, e) -> None:
        self._collapse.start(self.cfg.collapse_delay_ms)

    def dropEvent(self, e) -> None:
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        self.shelf.add(paths)
        self._dropping = False
        self.mascot.flash("happy", 1.5)
        e.acceptProposedAction()
        self._kick()
        self.update()

    # ------------------------------------------------------------------ ghost
    def _fade_to(self, opacity: float) -> None:
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(opacity)
        self._fade.start()

    def _enter_ghost(self) -> None:
        """Double click: vanish and let clicks through until the cursor leaves the island's area."""
        self._ghost = True
        self._expand.stop()
        self._collapse.stop()
        self._anim.stop()
        set_click_through(int(self.winId()), True)
        self._fade_to(self.cfg.ghost_opacity)
        self._ghost_poll.start(50)

    def _check_ghost(self) -> None:
        if self.geometry().adjusted(-4, -4, 4, 4).contains(QCursor.pos()):
            return
        self._ghost_poll.stop()
        self._ghost = False
        set_click_through(int(self.winId()), False)
        self._fade_to(1.0)
        self._hover = self._dropping = False
        self._apply_mode()
        self._kick()

    def mouseDoubleClickEvent(self, e) -> None:
        if e.button() == Qt.LeftButton and self._hit(e.position())[0] is None:
            self._enter_ghost()
        else:
            self.mousePressEvent(e)  # keep buttons responsive to rapid clicks

    # ------------------------------------------------------------------ mouse
    def _hit(self, pos: QPointF):
        for rect, kind, arg in reversed(self._hits):
            if rect.contains(pos):
                return kind, arg
        return None, None

    def mousePressEvent(self, e) -> None:
        if e.button() != Qt.LeftButton:
            return
        kind, arg = self._hit(e.position())
        self._press = (e.position(), "") if kind is None else (e.position(), kind)
        self._press_arg = arg
        if kind == "tile":
            return  # decided on release (open) or move (drag out)
        self._press = None
        m = self.media_svc
        if kind == "mascot":
            self.mascot.poke()
            self._kick()
        elif kind == "tab":
            self.tab = arg
        elif kind == "toggle":
            m.toggle()
        elif kind == "next":
            m.next()
        elif kind == "prev":
            m.previous()
        elif kind == "seek":
            m.seek(arg)
            self._media_stamp, self.media.position = time.monotonic(), arg
        elif kind == "bar":
            rect, dur = arg
            frac = (e.position().x() - rect.left()) / rect.width()
            t = max(0.0, min(1.0, frac)) * dur
            m.seek(t)
            self._media_stamp, self.media.position = time.monotonic(), t
        elif kind == "focus_toggle":
            self.focus.toggle(time.monotonic())
            self._apply_mode()
        elif kind == "focus_reset":
            self.focus.reset()
            self._apply_mode()
        elif kind == "focus_break":
            self.focus.start_break(time.monotonic())
            self._apply_mode()
        elif kind in ("focus_minus", "focus_plus"):
            self._focus_adjust(self.focus.step * (1 if kind == "focus_plus" else -1))
        elif kind == "focus_skip":
            self.focus.skip(time.monotonic())
            self._apply_mode()
        elif kind == "remove":
            self.shelf.remove(arg)
        elif kind in ("deny", "once", "always"):
            self.hub.resolve(arg, kind)
        self.update()

    def mouseMoveEvent(self, e) -> None:
        if not (self._press and self._press[1] == "tile" and e.buttons() & Qt.LeftButton):
            return
        if (e.position() - self._press[0]).manhattanLength() < 8:
            return
        path = self._press_arg
        self._press = None
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(path)])
        drag = QDrag(self)
        drag.setMimeData(mime)
        pm = self._icon(path)
        drag.setPixmap(pm)
        self._dragging_out = True
        drag.exec(Qt.CopyAction)
        self._dragging_out = False
        if not self.underMouse():
            self._collapse.start(self.cfg.collapse_delay_ms)

    def mouseReleaseEvent(self, e) -> None:
        if self._press and self._press[1] == "tile":
            try:
                os.startfile(self._press_arg)  # type: ignore[attr-defined]
            except (OSError, AttributeError):
                pass
        self._press = None

    # ----------------------------------------------------------------- painting
    def _icon(self, path: str) -> QPixmap:
        if path not in self._icons:
            self._icons[path] = self._icon_provider.icon(QFileInfo(path)).pixmap(32, 32)
        return self._icons[path]

    def _hit_rect(self, rect: QRectF, kind: str, arg=None) -> None:
        self._hits.append((rect, kind, arg))

    def paintEvent(self, _) -> None:
        self._hits.clear()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, min(r.height() / 2, 30), min(r.height() / 2, 30))
        mode = self.mode
        if self._claude and mode == "compact":
            grad = QLinearGradient(0, 0, r.width(), 0)
            grad.setColorAt(0, QColor("#F2A987"))
            grad.setColorAt(1, CLAUDE)
            p.fillPath(path, grad)
        else:
            p.fillPath(path, CLAUDE_DARK if self._claude else BG)
        p.setClipPath(path)

        {
            "compact": self._paint_compact,
            "toast": self._paint_toast,
            "peek": self._paint_peek,
            "approval": self._paint_approval,
            "expanded": self._paint_expanded,
        }[mode](p, r)
        p.end()

    def _text(self, p, rect: QRectF, text: str, color=TEXT, size=10, bold=False, align=Qt.AlignLeft):
        f = QFont(FONT, size)
        f.setBold(bold)
        p.setFont(f)
        p.setPen(color)
        el = QFontMetrics(f).elidedText(text, Qt.ElideRight, int(rect.width()))
        p.drawText(rect, int(align | Qt.AlignVCenter), el)

    def _mascot_at(self, p, rect: QRectF) -> None:
        self.mascot.paint(p, rect)
        self._hit_rect(rect, "mascot")

    def _paint_compact(self, p, r: QRectF) -> None:
        self._mascot_at(p, QRectF(10, (r.height() - 26) / 2, 26, 26))
        playing = self.media.active and self.media.playing and not self._claude and not self.focus.active
        if self._claude:
            self._text(p, QRectF(46, 0, r.width() - 46 - 36, r.height()), self._compact_text(), CLAUDE_INK, 10, True)
            pulse = 3.2 + 1.2 * math.sin(time.monotonic() * 4)
            p.setPen(Qt.NoPen)
            p.setBrush(CLAUDE_INK)
            p.drawEllipse(QPointF(r.width() - 22, r.height() / 2), pulse, pulse)
        elif self.focus.active:
            self._text(p, QRectF(46, 0, r.width() - 46 - 40, r.height()), self._compact_text(), size=10)
            self._ring(p, QRectF(r.width() - 32, r.height() / 2 - 9, 18, 18), self.focus.progress, 3.0,
                       self.accent if self.focus.phase == WORK else GREEN)
        elif playing:
            self._text(p, QRectF(46, 0, r.width() - 46 - 40, r.height()), self._compact_text(), size=10)
        else:  # just the clock: centred in the whole pill
            self._text(p, QRectF(0, 0, r.width(), r.height()), self._compact_text(), size=10, align=Qt.AlignHCenter)
        if playing:
            self._equalizer(p, QRectF(r.width() - 34, r.height() / 2 - 8, 20, 16))

    def _equalizer(self, p, rect: QRectF) -> None:
        t = time.monotonic()
        p.setPen(Qt.NoPen)
        p.setBrush(self.accent)
        for i in range(3):
            h = rect.height() * (0.35 + 0.65 * abs(math.sin(t * (3 + i * 1.3) + i)))
            p.drawRoundedRect(QRectF(rect.left() + i * 7, rect.bottom() - h, 4, h), 2, 2)

    def _paint_toast(self, p, r: QRectF) -> None:
        kind, text = self._toast or ("", "")
        self._mascot_at(p, QRectF(10, (r.height() - 26) / 2, 26, 26))
        color = GREEN if kind == "done" else AMBER
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawEllipse(QPointF(54, r.height() / 2), 4, 4)
        self._text(p, QRectF(66, 0, r.width() - 80, r.height()), text, size=10, bold=True)

    def _paint_peek(self, p, r: QRectF) -> None:
        kind, title, sub, pct, start = self._peek or ("", "", "", 0, time.monotonic())
        t = time.monotonic() - start
        h = r.height()
        if kind in ("charging", "battery"):
            self._paint_battery(p, QRectF(16, h / 2 - 11, 40, 22), kind == "charging", pct, t)
            self._text(p, QRectF(70, 8, r.width() - 150, 22), title, TEXT, 11, True)
            self._text(p, QRectF(70, 29, r.width() - 150, 20), sub, DIM, 9)
            self._text(p, QRectF(r.width() - 80, 0, 62, h), f"{pct}%", TEXT, 16, True, Qt.AlignRight)
        else:
            m = QRectF(14, h / 2 - 18, 36, 36)
            self.mascot.paint(p, m)
            if kind == "headphones":
                self._paint_headphones(p, m)
                self._paint_waves(p, QPointF(r.width() - 30, h / 2), t)
            elif kind == "headphones_off":
                self._paint_headphones(p, m, dim=True)
            self._text(p, QRectF(62, 8, r.width() - 110, 22), title, TEXT, 11, True)
            self._text(p, QRectF(62, 29, r.width() - 110, 20), sub, DIM, 9)

    @staticmethod
    def _paint_headphones(p, m: QRectF, dim: bool = False) -> None:
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        col = QColor(DIM) if dim else QColor(TEXT)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(col, 3.4, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(m.left() + 3, m.top() + 1, m.width() - 6, m.height() * 0.8), 0, 180 * 16)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#6E5BD6") if not dim else QColor(DIM).darker(150))
        cy = m.center().y()
        p.drawRoundedRect(QRectF(m.left() - 1, cy - 8, 9, 17), 3.5, 3.5)
        p.drawRoundedRect(QRectF(m.right() - 8, cy - 8, 9, 17), 3.5, 3.5)
        p.restore()

    @staticmethod
    def _paint_waves(p, c: QPointF, t: float) -> None:
        p.save()
        p.setBrush(Qt.NoBrush)
        for i in range(3):
            phase = (t * 1.6 - i * 0.28) % 1.0
            alpha = int(255 * (1 - phase) * min(1.0, t * 3))
            p.setPen(QPen(QColor(185, 167, 255, alpha), 2.2, Qt.SolidLine, Qt.RoundCap))
            rad = 5 + phase * 16
            p.drawArc(QRectF(c.x() - rad, c.y() - rad, rad * 2, rad * 2), -50 * 16, 100 * 16)
        p.restore()

    @staticmethod
    def _paint_battery(p, body: QRectF, charging: bool, pct: int, t: float) -> None:
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(TEXT, 2))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(body, 6, 6)
        p.setPen(Qt.NoPen)
        p.setBrush(TEXT)
        p.drawRoundedRect(QRectF(body.right() + 2, body.center().y() - 4, 3.5, 8), 1.5, 1.5)
        ease = 1 - (1 - min(t / 0.7, 1.0)) ** 3  # fill rises on arrival
        frac = max(0.06, pct / 100) * ease
        color = GREEN if charging or pct > 20 else RED
        if charging:
            color = QColor(color)
            color.setAlphaF(0.75 + 0.25 * math.sin(t * 5))
        inner = body.adjusted(3.5, 3.5, -3.5, -3.5)
        p.setBrush(color)
        p.drawRoundedRect(QRectF(inner.left(), inner.top(), inner.width() * frac, inner.height()), 3, 3)
        if charging and t > 0.15:
            c = body.center()
            bolt = QPolygonF([
                QPointF(c.x() + 2, c.y() - 9), QPointF(c.x() - 6, c.y() + 1.5), QPointF(c.x() - 0.5, c.y() + 1.5),
                QPointF(c.x() - 2, c.y() + 9), QPointF(c.x() + 6, c.y() - 2), QPointF(c.x() + 0.5, c.y() - 2),
            ])
            p.setPen(QPen(BG, 1.4))
            p.setBrush(QColor("#FFF3B0"))
            p.drawPolygon(bolt)
        p.restore()

    def _paint_approval(self, p, r: QRectF) -> None:
        ap = self.approvals[0]
        self._mascot_at(p, QRectF(16, 16, 36, 36))
        sess = self.hub.sessions.get(ap.session_id)
        who = sess.project if sess else "Claude"
        self._text(p, QRectF(66, 14, r.width() - 150, 22), f"{who} wants to use {ap.tool}", size=11, bold=True)
        if len(self.approvals) > 1:
            self._text(p, QRectF(r.width() - 90, 14, 74, 22), f"+{len(self.approvals) - 1} more", DIM, 9, align=Qt.AlignRight)
        self._text(p, QRectF(66, 38, r.width() - 82, 22), ap.summary, DIM, 10)
        # Deny | Allow always | Allow once (default, emphasised)
        y = r.height() - 48
        once = QRectF(r.width() - 18 - 124, y - 1, 124, 36)
        always = QRectF(once.left() - 8 - 108, y + 1, 108, 32)
        deny = QRectF(always.left() - 8 - 70, y + 1, 70, 32)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(DIM, 1.2))
        p.drawRoundedRect(deny, 16, 16)
        self._text(p, deny, "Deny", TEXT, 10, align=Qt.AlignHCenter)
        ok = ap.can_always
        p.setPen(QPen(self.accent if ok else QColor(255, 255, 255, 30), 1.2))
        p.drawRoundedRect(always, 16, 16)
        self._text(p, always, "Allow always", self.accent if ok else DIM, 10, align=Qt.AlignHCenter)
        halo = QColor(self.accent)
        halo.setAlpha(60)
        p.setPen(QPen(halo, 3))
        p.setBrush(self.accent)
        p.drawRoundedRect(once.adjusted(-1, -1, 1, 1), 18, 18)
        self._text(p, once, "Allow once", CLAUDE_INK if self._claude else BG, 10, True, Qt.AlignHCenter)
        self._hit_rect(deny, "deny", ap.id)
        if ok:
            self._hit_rect(always, "always", ap.id)
        self._hit_rect(once, "once", ap.id)

    def _paint_expanded(self, p, r: QRectF) -> None:
        self._mascot_at(p, QRectF(14, 8, 34, 34))
        x = 60.0
        for name in TABS:
            tab = QRectF(x, 12, 84, 26)
            if name == self.tab:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(255, 255, 255, 30))
                p.drawRoundedRect(tab, 13, 13)
            self._text(p, tab, name, TEXT if name == self.tab else DIM, 10, name == self.tab, Qt.AlignHCenter)
            self._hit_rect(tab, "tab", name)
            x += 90
        self._text(p, QRectF(r.width() - 70, 12, 56, 26), time.strftime("%H:%M"), DIM, 10, align=Qt.AlignRight)
        {
            "Music": self._paint_music, "Focus": self._paint_focus,
            "Shelf": self._paint_shelf, "Agents": self._paint_agents,
        }[self.tab](p, r)

    @staticmethod
    def _ring(p, rect: QRectF, progress: float, width: float, color: QColor) -> None:
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 36), width, Qt.SolidLine, Qt.RoundCap))
        p.drawEllipse(rect)
        if progress > 0:
            p.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(rect, 90 * 16, -int(progress * 360 * 16))
        p.restore()

    def _pill_button(self, p, rect: QRectF, text: str, kind: str, filled: QColor | None = None, enabled: bool = True) -> None:
        r = rect.height() / 2
        if filled is not None:
            p.setPen(Qt.NoPen)
            p.setBrush(filled)
            p.drawRoundedRect(rect, r, r)
            self._text(p, rect, text, CLAUDE_INK if self._claude else BG, 11, True, Qt.AlignHCenter)
        else:
            p.setPen(QPen(DIM if enabled else QColor(255, 255, 255, 30), 1.2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(rect, r, r)
            self._text(p, rect, text, TEXT if enabled else DIM, 10, align=Qt.AlignHCenter)
        if enabled:
            self._hit_rect(rect, kind)

    def _paint_focus(self, p, r: QRectF) -> None:
        f = self.focus
        color = self.accent if f.phase == WORK else GREEN
        ring = QRectF(30, 60, 140, 140)
        self._ring(p, ring, f.progress, 9.0, color)
        cy = ring.center().y()
        self._text(p, QRectF(ring.left(), cy - 30, ring.width(), 40), format_clock(f.remaining), TEXT, 24, True, Qt.AlignHCenter)
        sub = "paused" if f.active and not f.running else f.label.lower()
        self._text(p, QRectF(ring.left(), cy + 8, ring.width(), 20), sub, DIM, 10, align=Qt.AlignHCenter)
        # length: -/+ (scroll wheel over the island works too)
        for dx, sign, kind in ((-26, "−", "focus_minus"), (26, "+", "focus_plus")):
            b = QRectF(ring.center().x() + dx - 12, cy + 32, 24, 24)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 28))
            p.drawEllipse(b)
            self._text(p, b, sign, TEXT, 12, True, Qt.AlignHCenter)
            self._hit_rect(b, kind)

        x = 204.0
        self._text(p, QRectF(x, 58, r.width() - x - 16, 28), f.label, TEXT, 15, True)
        filled, total = f.session_dots
        if f.interrupted is not None:
            line = "Focus resumes after"
        elif f.phase == LONG:
            line = "Session complete"
        else:
            line = f"Session {min(filled + (1 if f.phase == WORK else 0), total)} of {total}"
        self._text(p, QRectF(x, 85, r.width() - x - 16, 22), line, DIM, 10)
        p.setPen(Qt.NoPen)
        for i in range(total):
            p.setBrush(color if i < filled else QColor(255, 255, 255, 36))
            p.drawEllipse(QPointF(x + 7 + i * 20, 123), 6, 6)

        label = "Pause" if f.running else ("Resume" if f.active else "Start")
        self._pill_button(p, QRectF(x, 146, 124, 36), label, "focus_toggle", color)
        if f.interrupted is None:
            self._pill_button(p, QRectF(x + 132, 148, 88, 32), "Break", "focus_break", enabled=f.can_break)
        row2 = 192
        self._pill_button(p, QRectF(x, row2, 78, 30), "Reset", "focus_reset")
        self._pill_button(p, QRectF(x + 86, row2, 116, 30), "Resume focus" if f.interrupted is not None else "Skip", "focus_skip")

    def _paint_music(self, p, r: QRectF) -> None:
        m = self.media
        if not m.active:
            self._text(p, QRectF(0, 50, r.width(), r.height() - 60), "Nothing playing", DIM, 11, align=Qt.AlignHCenter)
            return
        art = QRectF(18, 54, 76, 76)
        path = QPainterPath()
        path.addRoundedRect(art, 14, 14)
        if self._art:
            p.save()
            p.setClipPath(path)
            p.drawPixmap(art.toRect(), self._art.scaled(76, 76, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
            p.restore()
        else:
            p.fillPath(path, QColor(255, 255, 255, 25))
            self._text(p, art, "♪", self.accent, 26, align=Qt.AlignHCenter)
        tx = 108.0
        self._text(p, QRectF(tx, 52, r.width() - tx - 18, 24), m.title, TEXT, 13, True)
        self._text(p, QRectF(tx, 76, r.width() - tx - 18, 20), m.artist, DIM, 10)

        pos, dur = self._position(), m.duration
        bar = QRectF(tx, 104, r.width() - tx - 70, 5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 40))
        p.drawRoundedRect(bar, 2.5, 2.5)
        if dur > 0:
            p.setBrush(self.accent)
            p.drawRoundedRect(QRectF(bar.left(), bar.top(), bar.width() * min(pos / dur, 1), 5), 2.5, 2.5)
            self._hit_rect(bar.adjusted(0, -8, 0, 8), "bar", (bar, dur))
        self._text(p, QRectF(bar.right() + 8, 98, 56, 16), f"{fmt_time(pos)}", DIM, 8)

        cy, cx = 124 + 10, tx + 60
        self._control(p, "prev", QPointF(cx - 46, cy + 4))
        self._control(p, "play" if not m.playing else "pause", QPointF(cx, cy + 4), 15)
        self._control(p, "next", QPointF(cx + 46, cy + 4))
        self._paint_lyrics(p, r, pos)

    def _control(self, p, kind: str, c: QPointF, size: float = 11) -> None:
        hit = QRectF(c.x() - 18, c.y() - 18, 36, 36)
        p.setPen(Qt.NoPen)
        p.setBrush(TEXT)
        s = size
        if kind == "play":
            p.drawPolygon(QPolygonF([QPointF(c.x() - s * .5, c.y() - s * .7), QPointF(c.x() - s * .5, c.y() + s * .7), QPointF(c.x() + s * .7, c.y())]))
        elif kind == "pause":
            p.drawRoundedRect(QRectF(c.x() - s * .55, c.y() - s * .7, s * .4, s * 1.4), 1.5, 1.5)
            p.drawRoundedRect(QRectF(c.x() + s * .15, c.y() - s * .7, s * .4, s * 1.4), 1.5, 1.5)
        elif kind == "next":
            p.drawPolygon(QPolygonF([QPointF(c.x() - s * .6, c.y() - s * .6), QPointF(c.x() - s * .6, c.y() + s * .6), QPointF(c.x() + s * .35, c.y())]))
            p.drawRect(QRectF(c.x() + s * .45, c.y() - s * .6, s * .22, s * 1.2))
        elif kind == "prev":
            p.drawPolygon(QPolygonF([QPointF(c.x() + s * .6, c.y() - s * .6), QPointF(c.x() + s * .6, c.y() + s * .6), QPointF(c.x() - s * .35, c.y())]))
            p.drawRect(QRectF(c.x() - s * .67, c.y() - s * .6, s * .22, s * 1.2))
        self._hit_rect(hit, "toggle" if kind in ("play", "pause") else kind)

    def _paint_lyrics(self, p, r: QRectF, pos: float) -> None:
        if not self.lines:
            msg = "Searching lyrics…" if self.cfg.lyrics_enabled and self._lines_key is None and self.media.title else "No synced lyrics"
            self._text(p, QRectF(0, 186, r.width(), 40), msg, DIM, 9, align=Qt.AlignHCenter)
            return
        i = current_index(self.lines, pos)
        for slot, idx in enumerate((i - 1, i, i + 1)):
            if not 0 <= idx < len(self.lines):
                continue
            line = self.lines[idx]
            rect = QRectF(20, 162 + slot * 25, r.width() - 40, 24)
            cur = idx == i
            self._text(p, rect, line.text or "♪", TEXT if cur else DIM, 12 if cur else 10, cur, Qt.AlignHCenter)
            self._hit_rect(rect, "seek", line.time)

    def _paint_shelf(self, p, r: QRectF) -> None:
        items = self.shelf.items
        area = QRectF(14, 52, r.width() - 28, r.height() - 66)
        if self._dropping or not items:
            p.setPen(QPen(self.accent if self._dropping else QColor(255, 255, 255, 50), 1.5, Qt.DashLine))
            p.setBrush(QColor(185, 167, 255, 25) if self._dropping else Qt.NoBrush)
            p.drawRoundedRect(area, 18, 18)
            msg = "Release to add" if self._dropping else "Drop files here"
            self._text(p, area, msg, self.accent if self._dropping else DIM, 12, align=Qt.AlignHCenter)
            if self._dropping or not items:
                return
        cols, tw, th = 4, 114, 82
        for n, item in enumerate(items[:8]):
            col, row = n % cols, n // cols
            tile = QRectF(area.left() + col * (tw + 5), area.top() + row * (th + 6), tw, th)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 18))
            p.drawRoundedRect(tile, 14, 14)
            p.drawPixmap(int(tile.center().x() - 16), int(tile.top() + 8), self._icon(item.path))
            self._text(p, QRectF(tile.left() + 6, tile.top() + 44, tw - 12, 18), item.name, TEXT, 9, align=Qt.AlignHCenter)
            self._text(p, QRectF(tile.left() + 6, tile.top() + 61, tw - 12, 16), item.size_text, DIM, 8, align=Qt.AlignHCenter)
            x = QRectF(tile.right() - 20, tile.top() + 3, 18, 18)
            self._text(p, x, "×", DIM, 11, align=Qt.AlignHCenter)
            self._hit_rect(tile, "tile", item.path)
            self._hit_rect(x, "remove", item.path)
        if len(items) > 8:
            self._text(p, QRectF(r.width() - 90, r.height() - 22, 76, 16), f"+{len(items) - 8} more", DIM, 8, align=Qt.AlignRight)

    def _paint_agents(self, p, r: QRectF) -> None:
        sessions = self.hub.snapshot()
        if not sessions:
            self._text(p, QRectF(20, 56, r.width() - 40, 30), "No agents connected", TEXT, 11, True, Qt.AlignHCenter)
            self._text(p, QRectF(20, 86, r.width() - 40, 40), "Run  python -m isla install-hooks  then start Claude Code", DIM, 9, align=Qt.AlignHCenter)
            return
        for n, s in enumerate(sessions[:5]):
            y = 54 + n * 34
            running = s is self._claude or (self._claude and s.id == self._claude.id)
            p.setPen(Qt.NoPen)
            p.setBrush(CLAUDE if running else STATUS_COLOR.get(s.status, DIM))
            p.drawEllipse(QPointF(30, y + 14), 5, 5)
            self._text(p, QRectF(46, y, 110, 28), s.project, TEXT, 10, True)
            stats = ""
            if running:
                stats = fmt_minutes(s.elapsed) + (f" · {fmt_tokens(s.tokens)}" if s.tokens is not None else "")
                self._text(p, QRectF(r.width() - 140, y, 124, 28), stats, CLAUDE, 10, True, Qt.AlignRight)
            self._text(p, QRectF(160, y, r.width() - 160 - (150 if stats else 20), 28), s.activity, DIM, 10)
