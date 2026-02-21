"""Left-hand sidebar: event config, output config, store API config."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)
from typing import TYPE_CHECKING

from preprocessor import store_api

import preprocessor.config as cfg

if TYPE_CHECKING:
    from preprocessor.main_window import MainWindow


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setProperty("heading", True)
    return lbl


def _separator() -> QWidget:
    sep = QWidget()
    sep.setFixedHeight(1)
    sep.setProperty("separator", True)
    return sep


class Sidebar(QScrollArea):
    def __init__(self, parent: QWidget | None = None, window: "MainWindow | None" = None) -> None:
        super().__init__(parent)
        self._window = window
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(
            self.horizontalScrollBarPolicy().ScrollBarAlwaysOff  # type: ignore[attr-defined]
        )
        self.setFrameShape(self.Shape.NoFrame)

        content = QWidget()
        self.setWidget(content)
        root = QVBoxLayout(content)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ── App title ─────────────────────────────────────────────────────────
        title = QLabel("Race Photo\nPreprocessor")
        title.setProperty("title", True)
        root.addWidget(title)
        root.addWidget(_separator())

        # ── Event ─────────────────────────────────────────────────────────────
        root.addWidget(_section_label("Event"))

        form_event = QFormLayout()
        form_event.setLabelAlignment(
            form_event.labelAlignment()  # type: ignore[arg-type]
        )
        form_event.setSpacing(8)
        form_event.setContentsMargins(0, 0, 0, 0)

        self.slug_input = QLineEdit(cfg.get_event_slug())
        self.slug_input.setPlaceholderText("e.g. bmc-indoors-2025")
        self.slug_input.editingFinished.connect(
            lambda: cfg.set_event_slug(self.slug_input.text().strip())
        )
        form_event.addRow("Slug", self.slug_input)

        self.name_input = QLineEdit(cfg.get_event_name())
        self.name_input.setPlaceholderText("e.g. BMC Indoors 2025")
        self.name_input.editingFinished.connect(
            lambda: cfg.set_event_name(self.name_input.text().strip())
        )
        form_event.addRow("Name", self.name_input)

        root.addLayout(form_event)
        root.addWidget(_separator())

        # ── Output ────────────────────────────────────────────────────────────
        root.addWidget(_section_label("Output"))

        self.output_input = QLineEdit(cfg.get_output_root())
        self.output_input.setPlaceholderText("Select output folder…")
        self.output_input.setReadOnly(True)
        self.output_input.editingFinished.connect(
            lambda: cfg.set_output_root(self.output_input.text().strip())
        )

        browse_btn = QPushButton("Browse…")
        browse_btn.setProperty("secondary", True)
        browse_btn.setMinimumWidth(96)
        browse_btn.clicked.connect(self._browse_output)

        output_row = QHBoxLayout()
        output_row.setSpacing(6)
        output_row.addWidget(self.output_input)
        output_row.addWidget(browse_btn)
        root.addLayout(output_row)

        # Resolved path preview
        self._output_preview = QLabel()
        self._output_preview.setProperty("hint", True)
        self._output_preview.setWordWrap(True)
        root.addWidget(self._output_preview)
        self._update_output_preview()
        self.slug_input.editingFinished.connect(self._update_output_preview)
        self.output_input.textChanged.connect(self._update_output_preview)

        root.addWidget(_separator())

        # ── Store API ─────────────────────────────────────────────────────────
        root.addWidget(_section_label("Store API"))

        form_api = QFormLayout()
        form_api.setSpacing(8)
        form_api.setContentsMargins(0, 0, 0, 0)

        self.store_url_input = QLineEdit(cfg.get_store_url())
        self.store_url_input.setPlaceholderText("https://your-store-url")
        self.store_url_input.editingFinished.connect(
            lambda: cfg.set_store_url(self.store_url_input.text().strip())
        )
        form_api.addRow("URL", self.store_url_input)

        self.store_token_input = QLineEdit(cfg.get_store_token())
        self.store_token_input.setPlaceholderText("admin token")
        self.store_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.store_token_input.editingFinished.connect(
            lambda: cfg.set_store_token(self.store_token_input.text().strip())
        )
        form_api.addRow("Token", self.store_token_input)

        root.addLayout(form_api)

        # Test connection row
        test_row = QHBoxLayout()
        test_row.setContentsMargins(0, 0, 0, 0)
        self._conn_test_btn = QPushButton("Test")
        self._conn_test_btn.setProperty("secondary", True)
        self._conn_test_btn.setFixedWidth(60)
        self._conn_test_btn.setToolTip("Test connection to the store API")
        self._conn_test_btn.clicked.connect(self._on_test_connection)
        self._conn_status_label = QLabel("")
        self._conn_status_label.setProperty("hint", True)
        self._conn_status_label.setWordWrap(True)
        test_row.addWidget(self._conn_test_btn)
        test_row.addWidget(self._conn_status_label, 1)
        root.addLayout(test_row)

        # ── Spacer ────────────────────────────────────────────────────────────
        root.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )

        # Footer row: version + theme toggle
        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 0, 0, 0)

        ver = QLabel("v0.2.0")
        ver.setProperty("hint", True)
        footer_row.addWidget(ver)
        footer_row.addStretch()

        self._theme_btn = QPushButton()
        self._theme_btn.setProperty("secondary", True)
        self._theme_btn.setFixedSize(28, 28)
        self._theme_btn.setToolTip("Toggle light / dark theme")
        self._theme_btn.clicked.connect(self._on_theme_toggle)
        self.update_theme_button(window.dark_mode if window else True)
        footer_row.addWidget(self._theme_btn)

        root.addLayout(footer_row)

    # ── Connection test ───────────────────────────────────────────────────────

    def _on_test_connection(self) -> None:
        url = self.store_url_input.text().strip() or cfg.get_store_url()
        token = self.store_token_input.text().strip() or cfg.get_store_token()
        self._conn_test_btn.setEnabled(False)
        self._conn_status_label.setText("Connecting…")
        self._conn_status_label.setStyleSheet("")

        class _Worker(QThread):
            done = Signal(bool, str)

            def __init__(self, url, token):
                super().__init__()
                self._url = url
                self._token = token

            def run(self):
                result = store_api.test_connection(self._url, self._token)
                self.done.emit(result.ok, result.message)

        self._test_worker = _Worker(url, token)
        self._test_worker.done.connect(self._on_test_done)
        self._test_worker.start()

    def _on_test_done(self, ok: bool, message: str) -> None:
        self._conn_test_btn.setEnabled(True)
        self._conn_status_label.setText(message)
        colour = "#4caf50" if ok else "#f44336"
        self._conn_status_label.setStyleSheet(f"color: {colour};")

    def _on_theme_toggle(self) -> None:
        if self._window:
            self._window.toggle_theme()

    def update_theme_button(self, dark: bool) -> None:
        self._theme_btn.setText("☀" if dark else "🌙")

    # ── Browse output folder ───────────────────────────────────────────────────
    def _browse_output(self) -> None:
        start = self.output_input.text() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Select output root", start)
        if folder:
            self.output_input.setText(folder)
            cfg.set_output_root(folder)
            self._update_output_preview()

    def _update_output_preview(self) -> None:
        root = self.output_input.text().strip()
        slug = self.slug_input.text().strip()
        if root and slug:
            proofs = str(Path(root) / "proofs" / slug)
            originals = str(Path(root) / "originals" / slug)
            self._output_preview.setText(
                f"proofs/…/{slug}/\noriginals/…/{slug}/"
            )
        elif root:
            self._output_preview.setText("Enter event slug to see resolved paths")
        else:
            self._output_preview.setText("")
