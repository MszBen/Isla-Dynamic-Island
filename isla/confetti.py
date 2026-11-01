"""Confetti burst: a click-through overlay that sprays from the island and falls away."""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget

PALETTES = {
    "claude": ["#D97757", "#F2A987", "#FFE3D3", "#FFC857", "#FFFFFF", "#B9A7FF"],
    "focus": ["#B9A7FF", "#5FD38D", "#FFC857", "#FF7AA8", "#9FB6FF", "#FFFFFF"],
}
GRAVITY = 720.0   # px/s^2
DRAG = 0.9        # fraction of velocity lost per second
LIFE = 2.4        # seconds
FADE = 0.7        # fade-out window at the end of life


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    angle: float
    spin: float
    w: float
    h: float
    color: QColor
    round: bool
    age: float = 0.0

    def advance(self, dt: float) -> None:
        self.vy += GRAVITY * dt
        k = max(0.0, 1.0 - DRAG * dt)
        self.vx *= k
        self.vy *= k
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.angle += self.spin * dt
        self.age += dt

    @property
    def alive(self) -> bool:
        return self.age < LIFE

    @property
    def opacity(self) -> float:
        return min(1.0, max(0.0, (LIFE - self.age) / FADE))


def spawn(count: int, origin: tuple[float, float], palette: list[str], rng: random.Random | None = None) -> list[Particle]:
    """A fan of pieces spraying outward and downward from `origin`."""
    rng = rng or random
    out = []
    for _ in range(count):
        ang = math.radians(rng.uniform(5, 175))  # 0 = right, 90 = straight down
        speed = rng.uniform(160, 560)
        size = rng.uniform(5, 10)
        out.append(Particle(
            x=origin[0] + rng.uniform(-70, 70), y=origin[1] + rng.uniform(-4, 4),
            vx=math.cos(ang) * speed, vy=math.sin(ang) * speed * 0.9 - 60,
            angle=rng.uniform(0, 360), spin=rng.uniform(-540, 540),
            w=size, h=size * rng.uniform(0.4, 0.9), color=QColor(rng.choice(palette)),
            round=rng.random() < 0.25,
        ))
    return out


class Confetti(QWidget):
    W, H = 680, 460

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.particles: list[Particle] = []
        self._last = time.monotonic()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def burst(self, style: str = "focus", count: int = 120) -> None:
        scr = QGuiApplication.primaryScreen().geometry()
        self.setGeometry(scr.x() + (scr.width() - self.W) // 2, scr.y(), self.W, self.H)
        self.particles += spawn(count, (self.W / 2, 30), PALETTES.get(style, PALETTES["focus"]))
        self._last = time.monotonic()
        self.show()
        if not self._timer.isActive():
            self._timer.start(16)

    def _tick(self) -> None:
        now = time.monotonic()
        self.step(min(now - self._last, 0.05))
        self._last = now

    def step(self, dt: float) -> None:
        for p in self.particles:
            p.advance(dt)
        self.particles = [p for p in self.particles if p.alive and p.y < self.H + 20]
        if not self.particles:
            self._timer.stop()
            self.hide()
        self.update()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        for c in self.particles:
            col = QColor(c.color)
            col.setAlphaF(c.opacity)
            p.setBrush(col)
            p.save()
            p.translate(c.x, c.y)
            p.rotate(c.angle)
            # a fake "flip" as the piece tumbles: squash the height with a cosine
            flip = abs(math.cos(math.radians(c.angle * 1.7)))
            r = QRectF(-c.w / 2, -c.h / 2 * max(0.25, flip), c.w, c.h * max(0.25, flip))
            p.drawEllipse(r) if c.round else p.drawRect(r)
            p.restore()
        p.end()
