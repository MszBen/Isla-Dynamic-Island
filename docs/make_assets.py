"""Regenerates the README screenshots and GIFs from the real app (run: python docs/make_assets.py).

It drives an Island with made-up data, so no music/Claude session is needed. The island window
briefly appears at the top of your screen while frames are captured.
"""
from __future__ import annotations

import math
import random
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "assets"
OUT.mkdir(parents=True, exist_ok=True)

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402
from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from isla.agents import AgentHub, Approval  # noqa: E402
from isla.config import Config  # noqa: E402
from isla.island import Island  # noqa: E402
from isla.lyrics import parse_lrc  # noqa: E402
from isla.media import MediaInfo, MediaService  # noqa: E402
from isla.settings import SettingsWindow  # noqa: E402
from isla.shelf import Shelf  # noqa: E402
from isla.welcome import WelcomeWindow  # noqa: E402
from isla import app as isla_app  # noqa: E402

app = QApplication([])
app.setStyleSheet(isla_app.APP_STYLE)

tmp = Path(tempfile.mkdtemp())
(tmp / "lyrics").mkdir()
cfg = Config()
cfg.save = lambda *a, **k: None  # never touch the user's real config
hub = AgentHub(47980)
shelf = Shelf(tmp / "shelf.json")
for name, size in (("Holiday photos.zip", 48_000_000), ("Invoice-March.pdf", 220_000), ("notes.txt", 2_000), ("logo.png", 90_000)):
    f = tmp / name
    f.write_bytes(b"x" * min(size, 4096))
    shelf.add([str(f)])
isl = Island(cfg, MediaService(), hub, shelf, tmp / "lyrics")
isl.show()

LYRICS = parse_lrc("""
[01:10.00]Neon lights on a quiet street
[01:12.20]Every window hums a different tune
[01:14.40]I'm walking home with a borrowed beat
[01:16.60]Underneath a paper moon
[01:18.80]Hold the line, we're almost there
[01:21.00]Carry me through the silver air
""")


def album_art() -> QImage:
    img = QImage(300, 300, QImage.Format_ARGB32)
    p = QPainter(img)
    g = QLinearGradient(0, 0, 300, 300)
    g.setColorAt(0, QColor("#7C5CFF"))
    g.setColorAt(0.55, QColor("#FF7AA8"))
    g.setColorAt(1, QColor("#FFC857"))
    p.fillRect(img.rect(), g)
    p.setPen(QColor(255, 255, 255, 190))
    p.setBrush(Qt.NoBrush)
    for r in (60, 100, 140):
        p.drawEllipse(QPointF(150, 150), r, r)
    p.end()
    return img


ART = album_art()


def pump(seconds: float, per_frame=None, fps: int = 12):
    """Run the Qt event loop for `seconds`, calling per_frame(t) ~fps times a second."""
    start = time.monotonic()
    nxt = start
    while True:
        now = time.monotonic()
        if now - start >= seconds:
            break
        app.processEvents()
        if now >= nxt:
            if per_frame:
                per_frame(now - start)
            nxt += 1 / fps
        time.sleep(0.004)


# ---------------------------------------------------------------- composition
_rng = random.Random(7)


def backdrop(w: int, h: int, scale: float) -> Image.Image:
    """Soft purple/peach gradient 'wallpaper'."""
    W, H = int(w * scale), int(h * scale)
    img = Image.new("RGB", (W, H), "#14102A")
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(20 + 26 * t), int(16 + 12 * t), int(42 + 40 * t)))
    blobs = Image.new("RGB", (W, H), (0, 0, 0))
    bd = ImageDraw.Draw(blobs)
    for cx, cy, r, col in ((0.18, 0.9, 0.5, (110, 70, 230)), (0.85, 0.2, 0.45, (230, 120, 90)), (0.6, 1.0, 0.4, (255, 122, 168))):
        bd.ellipse([W * cx - W * r, H * cy - W * r * 0.7, W * cx + W * r, H * cy + W * r * 0.7], fill=col)
    blobs = blobs.filter(ImageFilter.GaussianBlur(W * 0.12))
    return Image.blend(img, Image.composite(blobs, img, Image.new("L", (W, H), 255)), 0.32)


def qimage_to_pil(q: QImage) -> Image.Image:
    q = q.convertToFormat(QImage.Format_RGBA8888)
    return Image.frombuffer("RGBA", (q.width(), q.height()), bytes(q.constBits()), "raw", "RGBA", q.bytesPerLine(), 1).copy()


def place(base: Image.Image, fg: Image.Image, x: int, y: int, shadow: bool = True) -> None:
    if shadow:
        a = fg.split()[3]
        sh = Image.new("RGBA", fg.size, (0, 0, 0, 0))
        sh.putalpha(a.point(lambda v: int(v * 0.55)))
        pad = 40
        big = Image.new("RGBA", (fg.width + pad * 2, fg.height + pad * 2), (0, 0, 0, 0))
        big.paste(sh, (pad, pad))
        big = big.filter(ImageFilter.GaussianBlur(14))
        base.paste(big, (x - pad, y - pad + 12), big)
    base.paste(fg, (x, y), fg)


def grab_island() -> Image.Image:
    return qimage_to_pil(isl.grab().toImage())


def confetti_layer(scale: float) -> Image.Image | None:
    c = isl.confetti
    if not c.isVisible() and not c.particles:
        return None
    q = QImage(c.W, c.H, QImage.Format_ARGB32_Premultiplied)
    q.fill(Qt.transparent)
    c.render(q)
    img = qimage_to_pil(q)
    return img.resize((int(c.W * scale), int(c.H * scale)), Image.LANCZOS) if scale != 1 else img


def frame(bg: Image.Image, width_logical: int, scale: float, with_confetti: bool = True) -> Image.Image:
    """One composited frame: island (and confetti) on the backdrop, positioned like on a real screen."""
    out = bg.convert("RGBA")
    shot = grab_island()
    dpr = shot.width / max(isl.width(), 1)
    shot = shot.resize((int(isl.width() * scale), int(isl.height() * scale)), Image.LANCZOS) if dpr != scale else shot
    place(out, shot, (out.width - shot.width) // 2, int(10 * scale))
    if with_confetti:
        layer = confetti_layer(scale)
        if layer is not None:
            out.alpha_composite(layer, ((out.width - layer.width) // 2, 0))
    return out.convert("RGB")


def settle(seconds: float = 0.8) -> None:
    pump(seconds, None, 10)


# ------------------------------------------------------------------ scenarios
def reset_state() -> None:
    isl._hover = isl._dropping = False
    isl.approvals.clear()
    isl._toast = isl._peek = None
    isl.media = MediaInfo()
    isl.lines = []
    isl.focus.reset()
    isl.confetti.particles.clear()
    isl.confetti.hide()
    for s in list(hub.sessions):
        hub.sessions.pop(s)
    isl._refresh_claude()
    isl._apply_mode()


def play_music() -> None:
    isl.media = MediaInfo(True, "Paper Moon", "The Quiet Hours", True, 70.0, 214.0)
    isl._media_stamp = time.monotonic()
    isl.lines = LYRICS
    isl._art = __import__("PySide6.QtGui", fromlist=["QPixmap"]).QPixmap.fromImage(ART)


def start_claude(minutes: float = 7.0, tokens: int = 24_800) -> None:
    hub.handle({"session_id": "demo", "hook_event_name": "UserPromptSubmit", "cwd": "C:/Users/you/projects/isla"})
    s = hub.sessions["demo"]
    s.started = time.time() - minutes * 60
    s.transcript, s._usage = "demo", {"m": tokens}
    s.activity = "Editing island.py"
    isl._refresh_claude()


def show(tab: str | None = None, hover: bool = True) -> None:
    isl._hover = hover
    if tab:
        isl.tab = tab
    isl._apply_mode()
    settle(0.9)


STATIC_W, STATIC_H, SCALE = 720, 340, 2.0


def screenshot(name: str, w: int = STATIC_W, h: int = STATIC_H) -> None:
    bg = backdrop(w, h, SCALE)
    img = frame(bg, w, SCALE)
    img.save(OUT / f"{name}.png", optimize=True)
    print("saved", name)


def make_screenshots() -> None:
    reset_state(); settle(0.4); screenshot("compact", 720, 90)
    reset_state(); play_music(); show("Music"); screenshot("music")
    reset_state(); isl.focus.configure(25 * 60, 5 * 60, 15 * 60, 4); isl.focus.running = True
    isl.focus._last = time.monotonic(); isl.focus.remaining = 16 * 60 + 12; isl.focus.done = 1
    show("Focus"); isl.focus.remaining = 16 * 60 + 12; screenshot("focus")
    reset_state(); show("Shelf"); screenshot("shelf")
    reset_state(); start_claude(); show("Agents"); screenshot("agents")
    reset_state(); start_claude(); settle(0.8); screenshot("claude", 720, 90)
    reset_state(); hub.sessions["demo"] = __import__("isla.agents", fromlist=["Session"]).Session("demo", cwd="C:/Users/you/projects/isla")
    isl.approvals = [Approval("demo", "Bash", "Running pytest -q", {"command": "pytest -q"},
                              [{"type": "addRules", "rules": [{"toolName": "Bash", "ruleContent": "pytest"}]}])]
    isl._apply_mode(); settle(0.9); screenshot("approval", 720, 190)
    reset_state(); isl.show_peek("charging", "Charging", "Charger connected", 64); settle(1.4); screenshot("peek-charging", 720, 100)
    reset_state(); isl.show_peek("headphones", "Headphones connected", "WH-1000XM5", seconds=6); settle(1.3); screenshot("peek-headphones", 720, 100)
    # confetti
    reset_state(); isl.celebrate("claude"); pump(0.7, None, 30)
    for p in isl.confetti.particles:
        pass
    bg = backdrop(720, 420, SCALE)
    frame(bg, 720, SCALE).save(OUT / "confetti.png", optimize=True)
    print("saved confetti")
    reset_state()


def make_window_shots() -> None:
    sw = SettingsWindow(cfg, hub, None)
    sw.resize(540, 1500)
    sw.show(); settle(0.5)
    shot = qimage_to_pil(sw.grab().toImage())
    shot.save(OUT / "settings.png", optimize=True)
    sw.close()
    wl = WelcomeWindow(None)
    wl.show(); settle(0.5)
    qimage_to_pil(wl.grab().toImage()).save(OUT / "welcome.png", optimize=True)
    wl.close()
    print("saved settings + welcome")


def make_hero(path: Path, fps: int = 12) -> None:
    scale, W, H = 1.0, 720, 320
    bg = backdrop(W, H, scale)
    frames: list[Image.Image] = []

    def cap(_t=None) -> None:
        frames.append(frame(bg, W, scale))

    reset_state(); play_music(); isl.media.playing = False
    isl.media = MediaInfo()
    pump(1.2, cap, fps)                                    # idle clock pill
    play_music(); isl._refresh_mood(); isl._apply_mode()
    pump(1.6, cap, fps)                                    # music + lyric in the pill
    isl._hover = True; isl.tab = "Music"; isl._apply_mode()
    pump(4.6, cap, fps)                                    # expanded music
    isl.tab = "Focus"; isl.focus.configure(25 * 60, 5 * 60, 15 * 60, 4); isl.focus.running = True
    isl.focus._last = time.monotonic(); isl.focus.done = 1

    def focus_frame(t: float) -> None:
        isl.focus.remaining = 16 * 60 - t * 40
        cap()

    pump(3.0, focus_frame, fps)                            # focus ring ticking
    isl.focus.reset(); isl.tab = "Shelf"; isl._dropping = True; isl._apply_mode()
    pump(1.4, cap, fps)                                    # drop target
    isl._dropping = False; isl._hover = True
    pump(2.0, cap, fps)                                    # shelf tiles
    isl._hover = False; isl.media = MediaInfo(); isl.lines = []
    start_claude(minutes=3.0, tokens=9_400); isl._apply_mode()
    pump(3.2, cap, fps)                                    # Claude orange pill
    hub.sessions["demo"].cwd = "C:/Users/you/projects/isla"
    isl.approvals = [Approval("demo", "Bash", "Running pytest -q", {"command": "pytest -q"},
                              [{"type": "addRules", "rules": [{"toolName": "Bash", "ruleContent": "pytest"}]}])]
    isl._apply_mode()
    pump(3.0, cap, fps)                                    # approval buttons
    isl.approvals.clear(); hub.handle({"session_id": "demo", "hook_event_name": "Stop"}); isl._refresh_claude()
    isl.celebrate("claude"); isl._apply_mode()

    def confetti_frame(_t: float) -> None:
        cap()

    pump(2.8, confetti_frame, fps)                         # confetti
    reset_state()
    pump(0.8, cap, fps)

    # GIF: palette-limited frames keep the file small
    pal = [f.quantize(colors=112, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=int(1000 / fps), loop=0, optimize=True, disposal=2)
    print(f"saved {path.name}: {len(frames)} frames, {path.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    which = sys.argv[1:] or ["shots", "windows", "hero"]
    if "shots" in which:
        make_screenshots()
    if "windows" in which:
        make_window_shots()
    if "hero" in which:
        make_hero(OUT / "hero.gif")
    isl.close()
