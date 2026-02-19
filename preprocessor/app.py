"""Application entry point."""
from __future__ import annotations

import sys

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from preprocessor.main_window import MainWindow

# ── Sky-blue accent values ────────────────────────────────────────────────────
#   primary  #0ea5e9   hover  #38bdf8   active  #0284c7

_SHARED = """
QMainWindow, QWidget {
    font-family: "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
}

/* ── Tab bar ─────────────────────────────────────────────────────────────── */
QTabWidget::pane {
    border: none;
}

QTabBar::tab {
    background: transparent;
    padding: 10px 22px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: 2px;
}

QTabBar::tab:hover:!selected {
    background: rgba(14, 165, 233, 0.06);
}

/* ── Buttons ─────────────────────────────────────────────────────────────── */
QPushButton {
    background-color: #0ea5e9;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 6px 18px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #38bdf8;
}

QPushButton:pressed {
    background-color: #0284c7;
}

/* ── Sliders ─────────────────────────────────────────────────────────────── */
QSlider::handle:horizontal {
    width: 14px;
    height: 14px;
    margin: -5px 0;
    background: #0ea5e9;
    border-radius: 7px;
}

QSlider::sub-page:horizontal {
    background: #0ea5e9;
    border-radius: 2px;
}

/* ── Scroll bars ─────────────────────────────────────────────────────────── */
QScrollBar:vertical {
    width: 6px;
    background: transparent;
    margin: 0;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QScrollBar:horizontal {
    height: 6px;
    background: transparent;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Progress bar ────────────────────────────────────────────────────────── */
QProgressBar {
    border: none;
    border-radius: 4px;
    text-align: center;
    color: transparent;
}

QProgressBar::chunk {
    background: #0ea5e9;
    border-radius: 4px;
}

/* ── Checkboxes ──────────────────────────────────────────────────────────── */
QCheckBox {
    spacing: 6px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
}

QCheckBox::indicator:checked {
    background: #0ea5e9;
    border-color: #0ea5e9;
}
"""

DARK_STYLESHEET = _SHARED + """
/* ── Dark base ───────────────────────────────────────────────────────────── */
QMainWindow, QWidget {
    background-color: #0b0f19;
    color: #e5e7eb;
}

QTabWidget::pane { background-color: #0f1420; }
QTabBar           { background: #0b0f19; }
QTabBar::tab      { color: #6b7280; }
QTabBar::tab:selected { color: #0ea5e9; border-bottom: 2px solid #0ea5e9; }

QPushButton:disabled { background-color: #1f2937; color: #4b5563; }

QPushButton[secondary="true"] {
    background-color: transparent; color: #9ca3af;
    border: 1px solid #2a3040; border-radius: 8px;
}
QPushButton[secondary="true"]:hover {
    background-color: #1a2030; color: #e5e7eb; border-color: #3a4560;
}

QLineEdit, QSpinBox, QComboBox {
    background-color: #161c2a; border: 1px solid #2a3040;
    border-radius: 6px; padding: 5px 10px; color: #e5e7eb;
    selection-background-color: #0ea5e9;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #0ea5e9; background-color: #1a2030;
}
QLineEdit:read-only { color: #6b7280; }
QSpinBox::up-button, QSpinBox::down-button { width: 0; }
QComboBox::drop-down { border: none; padding-right: 8px; }

QLabel { color: #e5e7eb; }
QLabel[heading="true"] { font-size: 10px; font-weight: 700; color: #4b5563; letter-spacing: 1.2px; }

QSlider::groove:horizontal { height: 4px; background: #1f2937; border-radius: 2px; }

QScrollBar::handle:vertical { background: #2a3040; border-radius: 3px; min-height: 24px; }
QScrollBar::handle:horizontal { background: #2a3040; border-radius: 3px; }

QProgressBar { background: #161c2a; }

QListWidget {
    background: #0f1420; border: none; border-radius: 10px; padding: 4px; outline: none;
}
QListWidget::item { color: #e5e7eb; border-radius: 6px; }
QListWidget::item:selected { background: rgba(14, 165, 233, 0.25); color: #38bdf8; }
QListWidget::item:hover:!selected { background: rgba(255,255,255,0.04); }

QTableWidget {
    background: #0f1420; alternate-background-color: #111827;
    border: none; border-radius: 10px; gridline-color: transparent; outline: none;
}
QTableWidget::item { padding: 3px 6px; border: none; }
QHeaderView::section {
    background: #0b0f19; color: #4b5563; font-size: 11px; font-weight: 600;
    letter-spacing: 0.5px; padding: 4px 6px; border: none; border-bottom: 1px solid #1a2030;
}

QCheckBox { color: #e5e7eb; }
QCheckBox::indicator { border: 1px solid #374151; background: #161c2a; }

QStatusBar {
    background: #0b0f19; border-top: 1px solid #161c2a;
    color: #4b5563; font-size: 12px; padding: 0 8px;
}
QSplitter::handle { background: #161c2a; width: 1px; }
QWidget[sidebar="true"] { background-color: #090d15; border-right: 1px solid #161c2a; }

QLabel[title="true"] { font-size: 14px; font-weight: 700; color: #0ea5e9; letter-spacing: 0.3px; }
QWidget[separator="true"] { background: #161c2a; }
QLabel[hint="true"] { font-size: 11px; color: #4b5563; }
"""

LIGHT_STYLESHEET = _SHARED + """
/* ── Light base ──────────────────────────────────────────────────────────── */
QMainWindow, QWidget {
    background-color: #f8fafc;
    color: #1e293b;
}

QTabWidget::pane { background-color: #ffffff; }
QTabBar           { background: #f1f5f9; }
QTabBar::tab      { color: #94a3b8; }
QTabBar::tab:selected { color: #0ea5e9; border-bottom: 2px solid #0ea5e9; }

QPushButton:disabled { background-color: #e2e8f0; color: #94a3b8; }

QPushButton[secondary="true"] {
    background-color: transparent; color: #64748b;
    border: 1px solid #cbd5e1; border-radius: 8px;
}
QPushButton[secondary="true"]:hover {
    background-color: #e2e8f0; color: #1e293b; border-color: #94a3b8;
}

QLineEdit, QSpinBox, QComboBox {
    background-color: #ffffff; border: 1px solid #cbd5e1;
    border-radius: 6px; padding: 5px 10px; color: #1e293b;
    selection-background-color: #0ea5e9;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #0ea5e9; background-color: #f0f9ff;
}
QLineEdit:read-only { color: #94a3b8; }
QSpinBox::up-button, QSpinBox::down-button { width: 0; }
QComboBox::drop-down { border: none; padding-right: 8px; }

QLabel { color: #1e293b; }
QLabel[heading="true"] { font-size: 10px; font-weight: 700; color: #94a3b8; letter-spacing: 1.2px; }

QSlider::groove:horizontal { height: 4px; background: #e2e8f0; border-radius: 2px; }

QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 3px; min-height: 24px; }
QScrollBar::handle:horizontal { background: #cbd5e1; border-radius: 3px; }

QProgressBar { background: #e2e8f0; }

QListWidget {
    background: #ffffff; border: none; border-radius: 10px; padding: 4px; outline: none;
}
QListWidget::item { color: #1e293b; border-radius: 6px; }
QListWidget::item:selected { background: rgba(14, 165, 233, 0.15); color: #0284c7; }
QListWidget::item:hover:!selected { background: rgba(0,0,0,0.04); }

QTableWidget {
    background: #ffffff; alternate-background-color: #f8fafc;
    border: none; border-radius: 10px; gridline-color: transparent; outline: none;
}
QTableWidget::item { padding: 3px 6px; border: none; }
QHeaderView::section {
    background: #f1f5f9; color: #94a3b8; font-size: 11px; font-weight: 600;
    letter-spacing: 0.5px; padding: 4px 6px; border: none; border-bottom: 1px solid #e2e8f0;
}

QCheckBox { color: #1e293b; }
QCheckBox::indicator { border: 1px solid #cbd5e1; background: #ffffff; }

QStatusBar {
    background: #f1f5f9; border-top: 1px solid #e2e8f0;
    color: #94a3b8; font-size: 12px; padding: 0 8px;
}
QSplitter::handle { background: #e2e8f0; width: 1px; }
QWidget[sidebar="true"] { background-color: #f1f5f9; border-right: 1px solid #e2e8f0; }

QLabel[title="true"] { font-size: 14px; font-weight: 700; color: #0ea5e9; letter-spacing: 0.3px; }
QWidget[separator="true"] { background: #e2e8f0; }
QLabel[hint="true"] { font-size: 11px; color: #64748b; }
"""


def get_stylesheet(dark: bool) -> str:
    return DARK_STYLESHEET if dark else LIGHT_STYLESHEET


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Race Photo Preprocessor")
    app.setOrganizationName("RacePhotoStore")

    settings = QSettings("RacePhotoStore", "Preprocessor")
    dark_mode = bool(settings.value("ui/dark_mode", True))

    app.setStyleSheet(get_stylesheet(dark_mode))

    window = MainWindow(dark_mode=dark_mode)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
