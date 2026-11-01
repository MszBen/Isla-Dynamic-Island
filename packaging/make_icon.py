"""Render the mascot into packaging/isla.ico (run by build.ps1)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402
from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402

from isla.mascot import Mascot  # noqa: E402

app = QGuiApplication([])
img = QImage(256, 256, QImage.Format_ARGB32)
img.fill(Qt.transparent)
p = QPainter(img)
Mascot().paint(p, QRectF(8, 8, 240, 240))
p.end()
png = ROOT / "packaging" / "isla.png"
img.save(str(png))
Image.open(png).save(ROOT / "packaging" / "isla.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icon written")
