"""Process tab — batch proof generation with live progress."""
from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from preprocessor.pipeline import ProcessConfig, ProcessResult
from preprocessor.workers.process_worker import ProcessWorker

if TYPE_CHECKING:
    from preprocessor.main_window import MainWindow

_STATUS_ICONS = {
    "ok":      ("✓", "#22c55e"),   # green
    "skipped": ("⚡", "#f97316"),  # orange
    "error":   ("✗", "#ef4444"),   # red
}


class ProcessTab(QWidget):
    def __init__(self, parent: "MainWindow") -> None:
        super().__init__(parent)
        self._window = parent
        self._worker: ProcessWorker | None = None
        self._start_time: float = 0.0
        self._total: int = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # ── Toolbar ──────────────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._start_btn = QPushButton("▶  Start Processing")
        self._start_btn.setObjectName("primary")
        self._start_btn.setFixedHeight(34)
        self._start_btn.clicked.connect(self._start)

        self._stop_btn = QPushButton("⏹  Stop")
        self._stop_btn.setFixedHeight(34)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop)

        toolbar.addWidget(self._start_btn)
        toolbar.addWidget(self._stop_btn)
        toolbar.addStretch()

        self._info_label = QLabel("Select images in the Import tab, then press Start.")
        self._info_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        toolbar.addWidget(self._info_label)

        root.addLayout(toolbar)

        # ── Progress bar ─────────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setFixedHeight(8)
        self._progress.setTextVisible(False)
        self._progress.hide()
        root.addWidget(self._progress)

        # ── Status line ──────────────────────────────────────────────────────
        status_row = QHBoxLayout()
        self._current_label = QLabel()
        self._current_label.setStyleSheet("color: #9ca3af; font-size: 12px;")
        self._eta_label = QLabel()
        self._eta_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        status_row.addWidget(self._current_label)
        status_row.addStretch()
        status_row.addWidget(self._eta_label)
        root.addLayout(status_row)

        # ── Results table ────────────────────────────────────────────────────
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels([" ", "File", "Message"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 28)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(1, 260)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._table.verticalHeader().setDefaultSectionSize(22)
        root.addWidget(self._table)

        # ── Summary footer ───────────────────────────────────────────────────
        self._summary = QLabel()
        self._summary.setStyleSheet("color: #6b7280; font-size: 12px; padding: 2px 0;")
        root.addWidget(self._summary)

    # ── Slots ────────────────────────────────────────────────────────────────

    def _start(self) -> None:
        paths = self._window.get_selected_images()
        if not paths:
            self._info_label.setText("No images selected — go to Import tab first.")
            return

        slug = self._window.get_event_slug()
        if not slug:
            self._info_label.setText("Event slug is empty — set it in the sidebar.")
            return

        import preprocessor.config as cfg
        output_root = cfg.get_output_root()
        if not output_root:
            self._info_label.setText("Output folder is not set — configure it in the sidebar.")
            return

        config = ProcessConfig(
            event_slug=slug,
            output_root=Path(output_root),
            watermark_text=cfg.get_watermark_text(),
            watermark_opacity=cfg.get_watermark_opacity(),
            watermark_position=cfg.get_watermark_position(),
            proof_size=cfg.get_proof_size(),
            proof_quality=cfg.get_proof_quality(),
            skip_existing=cfg.get_skip_existing(),
        )

        # Reset UI
        self._table.setRowCount(0)
        self._summary.clear()
        self._total = len(paths)
        self._start_time = time.monotonic()
        self._progress.setMaximum(self._total)
        self._progress.setValue(0)
        self._progress.show()
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._info_label.clear()

        self._worker = ProcessWorker(paths, config)
        self._worker.progress.connect(self._on_progress)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _stop(self) -> None:
        if self._worker and self._worker.isRunning():
            self._stop_btn.setEnabled(False)
            self._worker.stop()

    def _on_progress(self, current: int, total: int, path: str) -> None:
        self._progress.setValue(current - 1)
        fname = Path(path).name
        self._current_label.setText(f"Processing: {fname}  ({current}/{total})")

        elapsed = time.monotonic() - self._start_time
        if current > 1:
            per_file = elapsed / (current - 1)
            remaining = per_file * (total - current + 1)
            mins, secs = divmod(int(remaining), 60)
            self._eta_label.setText(f"ETA {mins}:{secs:02d}")

    def _on_file_done(self, result: ProcessResult) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)

        if result.skipped:
            key = "skipped"
            msg = "Skipped (already exists)"
        elif result.success:
            key = "ok"
            msg = "OK"
        else:
            key = "error"
            msg = result.error or "Unknown error"

        icon_text, color = _STATUS_ICONS[key]

        icon_item = QTableWidgetItem(icon_text)
        icon_item.setForeground(QColor(color))
        icon_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        file_item = QTableWidgetItem(Path(result.source).name)
        file_item.setToolTip(result.source)

        msg_item = QTableWidgetItem(msg)
        if key == "error":
            msg_item.setForeground(QColor("#ef4444"))

        self._table.setItem(row, 0, icon_item)
        self._table.setItem(row, 1, file_item)
        self._table.setItem(row, 2, msg_item)
        self._table.scrollToBottom()

    def _on_finished(self, results: list[ProcessResult]) -> None:
        self._progress.setValue(self._total)
        self._current_label.clear()
        self._eta_label.clear()
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

        total = len(results)
        ok = sum(1 for r in results if r.success and not r.skipped)
        skipped = sum(1 for r in results if r.skipped)
        errors = sum(1 for r in results if not r.success)

        elapsed = time.monotonic() - self._start_time
        mins, secs = divmod(int(elapsed), 60)
        self._summary.setText(
            f"Done — {ok} processed, {skipped} skipped, {errors} errors  "
            f"({mins}:{secs:02d} elapsed)"
        )
        self._window.set_status(
            f"Processing complete: {ok} ok, {skipped} skipped, {errors} errors"
        )

        if self._worker:
            self._worker.deleteLater()
            self._worker = None
