"""Process tab — batch proof generation with live progress and preview."""
from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
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
    "ok":      ("✔", "#22c55e"),
    "skipped": ("⚡", "#f59e0b"),
    "error":   ("✗", "#ef4444"),
}

_PLACEHOLDER_STYLE = "color: #4b5563; font-size: 12px;"


class ProcessTab(QWidget):
    def __init__(self, parent: "MainWindow") -> None:
        super().__init__(parent)
        self._window = parent
        self._worker: ProcessWorker | None = None
        self._start_time: float = 0.0
        self._total: int = 0
        self._config: ProcessConfig | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # ── Toolbar ───────────────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._start_btn = QPushButton("▶  Start Processing")
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
        self._info_label.setProperty("hint", True)
        toolbar.addWidget(self._info_label)

        root.addLayout(toolbar)

        # ── Progress bar ──────────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setFixedHeight(8)
        self._progress.setTextVisible(False)
        self._progress.hide()
        root.addWidget(self._progress)

        # ── Status line ───────────────────────────────────────────────────────
        status_row = QHBoxLayout()
        self._current_label = QLabel()
        self._current_label.setProperty("hint", True)
        self._eta_label = QLabel()
        self._eta_label.setProperty("hint", True)
        status_row.addWidget(self._current_label)
        status_row.addStretch()
        status_row.addWidget(self._eta_label)
        root.addLayout(status_row)

        # ── Body: results table (left) + preview panel (right) ────────────────
        body = QHBoxLayout()
        body.setSpacing(12)
        root.addLayout(body)

        # Left column: table + summary
        left_col = QVBoxLayout()
        left_col.setSpacing(6)
        body.addLayout(left_col, stretch=1)

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
        left_col.addWidget(self._table)

        self._summary = QLabel()
        self._summary.setProperty("hint", True)
        left_col.addWidget(self._summary)

        # Right column: live proof preview
        right_col = QVBoxLayout()
        right_col.setSpacing(4)
        body.addLayout(right_col, stretch=0)

        preview_heading = QLabel("LAST PROOF")
        preview_heading.setProperty("heading", True)
        right_col.addWidget(preview_heading)

        self._preview_label = QLabel()
        self._preview_label.setFixedSize(240, 200)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setProperty("previewPane", True)
        self._preview_label.setStyleSheet(
            "QLabel[previewPane='true'] { border-radius: 6px; }"
        )
        self._preview_label.setText("—")
        right_col.addWidget(self._preview_label)

        self._preview_name = QLabel()
        self._preview_name.setProperty("hint", True)
        self._preview_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_name.setWordWrap(True)
        self._preview_name.setFixedWidth(240)
        right_col.addWidget(self._preview_name)

        right_col.addStretch()

    # ── Slots ─────────────────────────────────────────────────────────────────

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

        self._config = ProcessConfig(
            event_slug=slug,
            output_root=Path(output_root),
            watermark_text=cfg.get_watermark_text(),
            watermark_opacity=cfg.get_watermark_opacity(),
            watermark_position=cfg.get_watermark_position(),
            proof_size=cfg.get_proof_size(),
            proof_quality=cfg.get_proof_quality(),
            skip_existing=cfg.get_skip_existing(),
        )

        self._table.setRowCount(0)
        self._summary.clear()
        self._preview_label.setText("—")
        self._preview_name.clear()
        self._total = len(paths)
        self._start_time = time.monotonic()
        self._progress.setMaximum(self._total)
        self._progress.setValue(0)
        self._progress.show()
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._info_label.clear()

        self._worker = ProcessWorker(paths, self._config)
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

        # Update live preview with the proof just generated
        if result.success and not result.skipped and self._config is not None:
            photo_id = Path(result.source).stem
            proof_path = (
                self._config.output_root
                / "proofs"
                / self._config.event_slug
                / f"{photo_id}.jpg"
            )
            self._load_preview(proof_path)

    def _load_preview(self, path: Path) -> None:
        if not path.exists():
            return
        px = QPixmap(str(path))
        if px.isNull():
            return
        scaled = px.scaled(
            self._preview_label.width(),
            self._preview_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_label.setPixmap(scaled)
        self._preview_name.setText(path.name)

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
