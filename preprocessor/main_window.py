"""Main application window."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QWidget,
)

from preprocessor.sidebar import Sidebar
from preprocessor.tabs.import_tab import ImportTab
from preprocessor.tabs.process_tab import ProcessTab
from preprocessor.tabs.bibs_tab import BibsTab
from preprocessor.tabs.deploy_tab import DeployTab


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Race Photo Preprocessor")
        self.resize(1280, 800)
        self.setMinimumSize(900, 600)

        # ── Central layout ────────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Splitter: sidebar | tabs ──────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        layout.addWidget(splitter)

        # Sidebar
        self.sidebar = Sidebar()
        self.sidebar.setProperty("sidebar", True)
        self.sidebar.setMinimumWidth(220)
        self.sidebar.setMaximumWidth(300)
        splitter.addWidget(self.sidebar)

        # Tab area
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        splitter.addWidget(self.tabs)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 1040])

        # ── Tabs ──────────────────────────────────────────────────────────────
        self.import_tab = ImportTab(self)
        self.process_tab = ProcessTab(self)
        self.bibs_tab = BibsTab(self)
        self.deploy_tab = DeployTab(self)

        self.tabs.addTab(self.import_tab, "  Import  ")
        self.tabs.addTab(self.process_tab, "  Process  ")
        self.tabs.addTab(self.bibs_tab, "  Bibs  ")
        self.tabs.addTab(self.deploy_tab, "  Deploy  ")

        # ── Status bar ────────────────────────────────────────────────────────
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready")

    # ── Public helpers ────────────────────────────────────────────────────────

    def set_status(self, message: str) -> None:
        self._status.showMessage(message)

    def get_event_slug(self) -> str:
        return self.sidebar.slug_input.text().strip()

    def get_selected_images(self) -> list[str]:
        return self.import_tab.selected_paths()
