"""Bibs tab — bib number tagging per photo. (Phase 5)"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from preprocessor.main_window import MainWindow


class BibsTab(QWidget):
    def __init__(self, parent: "MainWindow") -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)

        label = QLabel(
            "🏷  Bib number tagging\n\n"
            "Manual entry grid + future ML bib scanning\n"
            "will be built here in Phase 5."
        )
        label.setStyleSheet("color: #4b5563; font-size: 14px;")
        layout.addWidget(label)
        layout.addStretch()
