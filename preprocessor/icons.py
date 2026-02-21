"""Application icon helpers."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


def create_app_icon(size: int = 64) -> QIcon:
    """Return a minimalist camera-themed icon.

    Drawn at runtime so we don't need to manage binary resource files.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    body_color = QColor("#0ea5e9")
    stroke_color = QColor("#0284c7")
    lens_outer = QColor("#e0f2fe")
    lens_inner = QColor("#0369a1")

    # Camera body
    pen = QPen(stroke_color)
    pen.setWidth(max(2, size // 24))
    painter.setPen(pen)
    painter.setBrush(body_color)
    body_rect = (
        int(size * 0.12),
        int(size * 0.26),
        int(size * 0.76),
        int(size * 0.54),
    )
    painter.drawRoundedRect(*body_rect, size * 0.08, size * 0.08)

    # Top bump / viewfinder housing
    painter.drawRoundedRect(
        int(size * 0.26),
        int(size * 0.14),
        int(size * 0.2),
        int(size * 0.15),
        size * 0.03,
        size * 0.03,
    )

    # Lens rings
    cx = size // 2
    cy = int(size * 0.53)
    r_outer = int(size * 0.18)
    r_inner = int(size * 0.1)

    painter.setBrush(lens_outer)
    painter.setPen(QPen(stroke_color, max(2, size // 28)))
    painter.drawEllipse(cx - r_outer, cy - r_outer, r_outer * 2, r_outer * 2)

    painter.setBrush(lens_inner)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(cx - r_inner, cy - r_inner, r_inner * 2, r_inner * 2)

    # Small shutter/flash dot
    painter.setBrush(QColor("#f0f9ff"))
    painter.drawEllipse(int(size * 0.7), int(size * 0.36), int(size * 0.07), int(size * 0.07))

    painter.end()
    return QIcon(pixmap)