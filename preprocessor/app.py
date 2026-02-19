"""Application entry point."""
from __future__ import annotations

import sys

from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication

from preprocessor.main_window import MainWindow

# ── Dark orange palette matching race-photo-store theme ───────────────────────
STYLESHEET = """
QMainWindow, QWidget {
    background-color: #0b0f19;
    color: #e5e7eb;
    font-family: "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
}

QTabWidget::pane {
    border: 1px solid #2a2f3d;
    background-color: #111827;
}

QTabBar::tab {
    background: #1a1f2e;
    color: #9ca3af;
    padding: 8px 20px;
    border: 1px solid #2a2f3d;
    border-bottom: none;
}

QTabBar::tab:selected {
    background: #111827;
    color: #f97316;
    border-bottom: 2px solid #f97316;
}

QTabBar::tab:hover:!selected {
    color: #e5e7eb;
    background: #1e2535;
}

QPushButton {
    background-color: #f97316;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #fb923c;
}

QPushButton:pressed {
    background-color: #ea6c0a;
}

QPushButton:disabled {
    background-color: #374151;
    color: #6b7280;
}

QPushButton[secondary="true"] {
    background-color: #1f2937;
    color: #d1d5db;
    border: 1px solid #374151;
}

QPushButton[secondary="true"]:hover {
    background-color: #263044;
    color: #f3f4f6;
}

QLineEdit, QSpinBox, QComboBox {
    background-color: #1f2937;
    border: 1px solid #374151;
    border-radius: 4px;
    padding: 5px 8px;
    color: #e5e7eb;
    selection-background-color: #f97316;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #f97316;
}

QSlider::groove:horizontal {
    height: 4px;
    background: #374151;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    width: 14px;
    height: 14px;
    margin: -5px 0;
    background: #f97316;
    border-radius: 7px;
}

QSlider::sub-page:horizontal {
    background: #f97316;
    border-radius: 2px;
}

QScrollBar:vertical {
    width: 8px;
    background: transparent;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #374151;
    border-radius: 4px;
    min-height: 24px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QScrollBar:horizontal {
    height: 8px;
    background: transparent;
}

QScrollBar::handle:horizontal {
    background: #374151;
    border-radius: 4px;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QLabel {
    color: #e5e7eb;
}

QLabel[heading="true"] {
    font-size: 11px;
    font-weight: 700;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 1px;
}

QStatusBar {
    background: #0b0f19;
    border-top: 1px solid #1f2937;
    color: #6b7280;
    font-size: 12px;
}

QProgressBar {
    background: #1f2937;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: #e5e7eb;
    height: 6px;
}

QProgressBar::chunk {
    background: #f97316;
    border-radius: 4px;
}

QListWidget {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 6px;
}

QListWidget::item {
    color: #e5e7eb;
}

QListWidget::item:selected {
    background: #f97316;
    color: white;
}

QCheckBox {
    color: #e5e7eb;
    spacing: 6px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #4b5563;
    border-radius: 3px;
    background: #1f2937;
}

QCheckBox::indicator:checked {
    background: #f97316;
    border-color: #f97316;
}

QFrame[sidebar="true"] {
    background-color: #0d1117;
    border-right: 1px solid #1f2937;
}

QSplitter::handle {
    background: #1f2937;
    width: 1px;
}
"""


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Race Photo Preprocessor")
    app.setOrganizationName("RacePhotoStore")
    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
