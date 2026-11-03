"""Little search box under the island. The island itself never takes focus, so typing needs its own window."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLineEdit


class ClipSearch(QLineEdit):
    closed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setPlaceholderText("Search your clipboard…  (Enter to keep, Esc to clear)")
        self.setFixedHeight(34)
        self.setStyleSheet(
            "QLineEdit{background:#0C0B12;color:#F2F0FA;border:1px solid #B9A7FF;border-radius:17px;"
            "padding:0 14px;font:10pt 'Segoe UI';selection-background-color:#B9A7FF;selection-color:#0C0B12;}"
        )

    def open_at(self, x: int, y: int, width: int, text: str) -> None:
        self.setFixedWidth(width)
        self.setText(text)
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self.selectAll()

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key_Escape:
            self.clear()
            self.hide()
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.hide()
        else:
            super().keyPressEvent(e)

    def hideEvent(self, e) -> None:
        super().hideEvent(e)
        self.closed.emit()

    def focusOutEvent(self, e) -> None:
        super().focusOutEvent(e)
        self.hide()
