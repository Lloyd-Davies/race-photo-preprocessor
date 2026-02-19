"""Deploy tab — local copy or SFTP upload + store API ingest. (Phase 6-7)"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from preprocessor.main_window import MainWindow


class DeployTab(QWidget):
    def __init__(self, parent: "MainWindow") -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)

        label = QLabel(
            "🚀  Deploy to store\n\n"
            "Local copy, SFTP upload, and store API ingest trigger\n"
            "will be built here in Phases 6-7."
        )
        label.setStyleSheet("color: #4b5563; font-size: 14px;")
        layout.addWidget(label)
        layout.addStretch()
