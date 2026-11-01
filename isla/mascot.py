"""Isla the mascot: a vector blob with emotions, drawn with QPainter (no assets)."""
from __future__ import annotations

import math
import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen

BODY = QColor("#B9A7FF")
INK = QColor("#1B1530")
PINK = QColor("#FF7AA8")

EMOTIONS = ("idle", "happy", "curious", "focused", "wink", "love", "dizzy", "sleepy", "music")


class Mascot:
    def __init__(self) -> None:
        self.emotion = "idle"
        self.body = BODY  # tinted by the island while Claude is working
        self._until = 0.0  # temporary emotion expiry
        self._rest = "idle"
        self._next_blink = time.monotonic() + 2
        self._blink_end = 0.0
        self._pokes: list[float] = []

    # -- state ---------------------------------------------------------
    def set_rest(self, emotion: str) -> None:
        """Long-lived emotion (e.g. focused while an agent works)."""
        self._rest = emotion

    def flash(self, emotion: str, seconds: float = 3.0) -> None:
        """Short-lived emotion (e.g. happy for 3s when an agent finishes)."""
        self.emotion = emotion
        self._until = time.monotonic() + seconds

    def poke(self) -> None:
        now = time.monotonic()
        self._pokes = [t for t in self._pokes if now - t < 2.0] + [now]
        self.flash("dizzy" if len(self._pokes) >= 4 else "wink", 2.5)

    def update(self) -> None:
        now = time.monotonic()
        if now > self._until:
            self.emotion = self._rest
        if now > self._next_blink:
            self._blink_end = now + 0.12
            self._next_blink = now + random.uniform(2.5, 5.5)

    @property
    def animating(self) -> bool:
        return self.emotion != "idle" or time.monotonic() < self._blink_end

    # -- painting ------------------------------------------------------
    def paint(self, p: QPainter, rect: QRectF) -> None:
        t = time.monotonic()
        e = self.emotion
        blinking = t < self._blink_end and e in ("idle", "curious", "focused", "music")
        s = min(rect.width(), rect.height())
        cx, cy = rect.center().x(), rect.center().y()

        bob = 0.0
        tilt = 0.0
        if e in ("happy", "music"):
            bob = -abs(math.sin(t * (6 if e == "happy" else 4))) * s * 0.10
        elif e == "dizzy":
            tilt = math.sin(t * 9) * 14
        elif e == "curious":
            tilt = 9
        elif e == "sleepy":
            bob = math.sin(t * 1.5) * s * 0.03

        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(cx, cy + bob)
        p.rotate(tilt)
        u = s / 100.0
        p.scale(u, u)

        body = QPainterPath()
        body.addRoundedRect(QRectF(-40, -34, 80, 70), 32, 30)
        p.setPen(Qt.NoPen)
        p.setBrush(self.body)
        p.drawPath(body)
        p.setBrush(QColor(255, 255, 255, 60))  # highlight
        p.drawEllipse(QRectF(-26, -26, 20, 10))

        self._face(p, e, blinking, t)
        p.restore()

        if e == "curious":
            f = QFont("Segoe UI", max(6, int(s * 0.28)), QFont.Bold)
            p.setFont(f)
            p.setPen(QColor("#FFD36B"))
            p.drawText(QPointF(cx + s * 0.28, cy - s * 0.30), "?")
        elif e == "sleepy":
            p.setFont(QFont("Segoe UI", max(6, int(s * 0.22)), QFont.Bold))
            p.setPen(QColor("#9FB6FF"))
            p.drawText(QPointF(cx + s * 0.30, cy - s * 0.25 - (t * 6) % 6), "z")

    def _face(self, p: QPainter, e: str, blinking: bool, t: float) -> None:
        lx, rx, ey = -17, 17, -6
        ink = QPen(INK, 6, Qt.SolidLine, Qt.RoundCap)
        p.setBrush(INK)

        def dot(x: float, r: float = 7.5) -> None:
            p.setPen(Qt.NoPen)
            p.setBrush(INK)
            p.drawEllipse(QPointF(x, ey), r, r * (0.15 if blinking else 1.0))

        def arc_up(x: float) -> None:  # ^ happy eye
            p.setPen(ink)
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(x - 8, ey - 6, 16, 16), 20 * 16, 140 * 16)

        def arc_down(x: float) -> None:  # closed/sleepy eye
            p.setPen(ink)
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(x - 8, ey - 8, 16, 14), 200 * 16, 140 * 16)

        def heart(x: float) -> None:
            path = QPainterPath()
            path.moveTo(x, ey + 8)
            path.cubicTo(x - 14, ey - 2, x - 6, ey - 12, x, ey - 4)
            path.cubicTo(x + 6, ey - 12, x + 14, ey - 2, x, ey + 8)
            p.setPen(Qt.NoPen)
            p.setBrush(PINK)
            p.drawPath(path)

        def cross(x: float) -> None:
            p.setPen(ink)
            p.drawLine(QPointF(x - 5, ey - 5), QPointF(x + 5, ey + 5))
            p.drawLine(QPointF(x - 5, ey + 5), QPointF(x + 5, ey - 5))

        def mouth(kind: str) -> None:
            p.setPen(QPen(INK, 4, Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            if kind == "smile":
                p.drawArc(QRectF(-9, 8, 18, 12), 200 * 16, 140 * 16)
            elif kind == "o":
                p.drawEllipse(QPointF(0, 17), 3.5, 4.5)
            elif kind == "flat":
                p.drawLine(QPointF(-5, 17), QPointF(5, 17))

        if e in ("happy", "music"):
            arc_up(lx); arc_up(rx); mouth("smile")
        elif e == "love":
            heart(lx); heart(rx); mouth("smile")
        elif e == "wink":
            dot(lx); arc_up(rx); mouth("smile")
        elif e == "dizzy":
            cross(lx); cross(rx); mouth("o")
        elif e == "sleepy":
            arc_down(lx); arc_down(rx); mouth("flat")
        elif e == "focused":
            p.setPen(Qt.NoPen)
            p.setBrush(INK)
            for x in (lx, rx):
                p.drawRoundedRect(QRectF(x - 8, ey - 3, 16, 7 if not blinking else 2), 3, 3)
            p.setPen(QPen(INK, 3.5, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(lx - 8, ey - 9), QPointF(lx + 6, ey - 6))
            p.drawLine(QPointF(rx + 8, ey - 9), QPointF(rx - 6, ey - 6))
            mouth("flat")
        elif e == "curious":
            dot(lx, 7.5); dot(rx, 10); mouth("o")
        else:
            dot(lx); dot(rx)
