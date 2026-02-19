"""Process tab — watermark settings, proof generation, progress. (Phase 3)"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from preprocessor.main_window import MainWindow


class ProcessTab(QWidget):
    def __init__(self, parent: "MainWindow") -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)

        label = QLabel(
            "⚙  Processing pipeline\n\n"
            "Watermark settings, proof resize, and batch processing\n"
            "will be built here in Phase 3."
        )
        label.setStyleSheet("color: #4b5563; font-size: 14px;")
        layout.addWidget(label)
        layout.addStretch()
