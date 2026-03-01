"""Session step widget for workflow-first navigation."""
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from preprocessor.main_window import MainWindow


_SLUG_RE = re.compile(r"^[a-z0-9-]+$")


class SessionStep(QWidget):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self._window = window

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        title = QLabel("Session")
        title.setProperty("title", True)
        root.addWidget(title)

        desc = QLabel(
            "Review sidebar session fields (event, output, store API) and create a session "
            "before importing photos."
        )
        desc.setWordWrap(True)
        desc.setProperty("hint", True)
        root.addWidget(desc)

        self.validation_label = QLabel("")
        self.validation_label.setWordWrap(True)
        self.validation_label.setProperty("hint", True)
        root.addWidget(self.validation_label)

        self.create_session_button = QPushButton("Create Session")
        self.create_session_button.clicked.connect(self._on_create_session)
        root.addWidget(self.create_session_button, alignment=Qt.AlignmentFlag.AlignLeft)

        root.addStretch()

    def _validate(self) -> list[str]:
        missing: list[str] = []

        slug = self._window.sidebar.slug_input.text().strip()
        name = self._window.sidebar.name_input.text().strip()
        output_root = self._window.sidebar.output_input.text().strip()
        store_url = self._window.sidebar.store_url_input.text().strip()
        credential = self._window.sidebar.store_token_input.text().strip()

        if not name:
            missing.append("Event name is required")

        if not slug:
            missing.append("Event slug is required")
        elif _SLUG_RE.match(slug) is None:
            missing.append("Event slug must use lowercase letters, numbers, and hyphens")

        if not output_root:
            missing.append("Output root is required")
        else:
            root_path = Path(output_root)
            if not root_path.exists() and not root_path.parent.exists():
                missing.append("Output root does not exist and parent folder is unavailable")

        if not store_url:
            missing.append("Store URL is required")

        if not credential:
            missing.append("Admin credential is required")

        return missing

    def _on_create_session(self) -> None:
        problems = self._validate()
        if problems:
            self.validation_label.setStyleSheet("color: #f44336;")
            self.validation_label.setText("\n".join(f"• {msg}" for msg in problems))
            self._window.set_status("Session validation failed.")
            return

        self.validation_label.setStyleSheet("color: #4caf50;")
        self.validation_label.setText("Session is valid. Proceeding to Import.")
        self._window.complete_session()
