"""Process tab — batch proof generation with live progress and preview."""
from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import preprocessor.config as cfg
from preprocessor.pipeline import ProcessConfig, ProcessResult
from preprocessor.workers.process_worker import ProcessWorker
from preprocessor.workers.deploy_worker import DeployWorker
from preprocessor.bib_results import ensure_bib_csv

if TYPE_CHECKING:
    from preprocessor.main_window import MainWindow

_STATUS_ICONS = {
    "ok":      ("✔", "#22c55e"),
    "skipped": ("⚡", "#f59e0b"),
    "error":   ("✗", "#ef4444"),
}


class ProcessTab(QWidget):
    def __init__(self, parent: "MainWindow") -> None:
        super().__init__(parent)
        self._window = parent
        self._worker: ProcessWorker | None = None
        self._deploy_worker: DeployWorker | None = None
        self._start_time: float = 0.0
        self._total: int = 0
        self._config: ProcessConfig | None = None
        self._stop_requested: bool = False

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

        self._overwrite_cb = QCheckBox("Overwrite existing")
        self._overwrite_cb.setChecked(not cfg.get_skip_existing())
        self._overwrite_cb.setToolTip(
            "Re-process files that have already been output.\n"
            "Leave unchecked to skip photos that already exist on disk."
        )
        self._overwrite_cb.toggled.connect(
            lambda checked: cfg.set_skip_existing(not checked)
        )

        toolbar.addWidget(self._start_btn)
        toolbar.addWidget(self._stop_btn)
        toolbar.addWidget(self._overwrite_cb)

        self._auto_deploy_cb = QCheckBox("Auto-deploy after processing")
        self._auto_deploy_cb.setChecked(cfg.get_auto_deploy_after_process())
        self._auto_deploy_cb.setToolTip(
            "After processing completes with no errors, automatically upload proofs\n"
            "and originals to the store using the current Store API settings."
        )
        self._auto_deploy_cb.toggled.connect(cfg.set_auto_deploy_after_process)
        toolbar.addSpacing(12)
        toolbar.addWidget(self._auto_deploy_cb)

        toolbar.addStretch()

        self._info_label = QLabel("Select images in the Import tab, then press Start.")
        self._info_label.setProperty("hint", True)
        toolbar.addWidget(self._info_label)

        root.addLayout(toolbar)

        # ── Watermark settings ───────────────────────────────────────────────
        wm_group = QGroupBox("Watermark")
        wm_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        wm_form = QFormLayout(wm_group)
        wm_form.setContentsMargins(10, 8, 10, 8)
        wm_form.setSpacing(8)
        wm_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        wm_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        wm_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._wm_text = QLineEdit(cfg.get_watermark_text())
        self._wm_text.setPlaceholderText("© Race Photos")
        wm_form.addRow("Text", self._wm_text)

        self._wm_opacity = QSpinBox()
        self._wm_opacity.setRange(0, 100)
        self._wm_opacity.setValue(cfg.get_watermark_opacity())
        self._wm_opacity.setSuffix(" %")
        wm_form.addRow("Opacity", self._wm_opacity)

        self._wm_pattern = QComboBox()
        self._wm_pattern.addItem("Diagonal repeat", "diagonal-repeat")
        self._wm_pattern.addItem("Single corner", "single-corner")
        pattern_value = cfg.get_watermark_pattern()
        pattern_idx = max(0, self._wm_pattern.findData(pattern_value))
        self._wm_pattern.setCurrentIndex(pattern_idx)
        self._wm_pattern.currentIndexChanged.connect(self._on_pattern_changed)
        wm_form.addRow("Pattern", self._wm_pattern)

        self._wm_position = QComboBox()
        for pos in (
            "top-left", "top-center", "top-right",
            "center-left", "center", "center-right",
            "bottom-left", "bottom-center", "bottom-right",
        ):
            self._wm_position.addItem(pos, pos)
        pos_value = cfg.get_watermark_position()
        pos_idx = max(0, self._wm_position.findData(pos_value))
        self._wm_position.setCurrentIndex(pos_idx)
        wm_form.addRow("Position", self._wm_position)

        self._wm_angle = QSpinBox()
        self._wm_angle.setRange(-80, 80)
        self._wm_angle.setValue(cfg.get_watermark_angle())
        self._wm_angle.setSuffix("°")
        wm_form.addRow("Angle", self._wm_angle)

        self._wm_spacing_x = QSpinBox()
        self._wm_spacing_x.setRange(5, 70)
        self._wm_spacing_x.setValue(cfg.get_watermark_spacing_x_pct())
        self._wm_spacing_x.setSuffix(" %")
        wm_form.addRow("Spacing X", self._wm_spacing_x)

        self._wm_spacing_y = QSpinBox()
        self._wm_spacing_y.setRange(5, 70)
        self._wm_spacing_y.setValue(cfg.get_watermark_spacing_y_pct())
        self._wm_spacing_y.setSuffix(" %")
        wm_form.addRow("Spacing Y", self._wm_spacing_y)

        self._wm_font_scale = QSpinBox()
        self._wm_font_scale.setRange(50, 250)
        self._wm_font_scale.setValue(cfg.get_watermark_font_scale_pct())
        self._wm_font_scale.setSuffix(" %")
        wm_form.addRow("Font scale", self._wm_font_scale)

        root.addWidget(wm_group)
        self._on_pattern_changed()

        # ── Auto bib scan ─────────────────────────────────────────────────
        bib_group = QGroupBox("Auto bib scan")
        bib_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        bib_form = QFormLayout(bib_group)
        bib_form.setContentsMargins(10, 8, 10, 8)
        bib_form.setSpacing(8)
        bib_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        bib_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        bib_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._bib_enabled = QCheckBox("Enable auto bib scanning")
        self._bib_enabled.setChecked(cfg.get_auto_bib_scan_enabled())
        bib_form.addRow(self._bib_enabled)

        self._bib_backend = QComboBox()
        self._bib_backend.addItem("Disabled", "none")
        self._bib_backend.addItem("OCR (RapidOCR)", "ocr")
        backend_value = cfg.get_auto_bib_scan_backend()
        backend_idx = max(0, self._bib_backend.findData(backend_value))
        self._bib_backend.setCurrentIndex(backend_idx)
        bib_form.addRow("Backend", self._bib_backend)

        self._bib_min_conf = QSpinBox()
        self._bib_min_conf.setRange(1, 100)
        self._bib_min_conf.setValue(cfg.get_auto_bib_min_confidence())
        self._bib_min_conf.setSuffix(" %")
        bib_form.addRow("Min confidence", self._bib_min_conf)

        self._bib_enforce_min_digits = QCheckBox("Enforce minimum bib length")
        self._bib_enforce_min_digits.setChecked(cfg.get_auto_bib_enforce_min_digits())
        self._bib_enforce_min_digits.toggled.connect(self._on_bib_digits_toggle)
        bib_form.addRow(self._bib_enforce_min_digits)

        self._bib_min_digits = QSpinBox()
        self._bib_min_digits.setRange(1, 6)
        self._bib_min_digits.setValue(cfg.get_auto_bib_min_digits())
        bib_form.addRow("Min digits", self._bib_min_digits)
        self._on_bib_digits_toggle(self._bib_enforce_min_digits.isChecked())

        root.addWidget(bib_group)

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
            QMessageBox.warning(self, "No images selected", "Select images in the Import tab before processing.")
            return

        slug = self._window.get_event_slug()
        if not slug:
            self._info_label.setText("Event slug is empty — set it in the sidebar.")
            return

        output_root = cfg.get_output_root()
        if not output_root:
            self._info_label.setText("Output folder is not set — configure it in the sidebar.")
            return

        self._save_watermark_settings()

        self._config = ProcessConfig(
            event_slug=slug,
            output_root=Path(output_root),
            watermark_text=self._wm_text.text().strip(),
            watermark_opacity=self._wm_opacity.value(),
            watermark_pattern=self._wm_pattern.currentData(),
            watermark_position=self._wm_position.currentData(),
            watermark_angle=self._wm_angle.value(),
            watermark_spacing_x_pct=self._wm_spacing_x.value(),
            watermark_spacing_y_pct=self._wm_spacing_y.value(),
            watermark_font_scale_pct=self._wm_font_scale.value(),
            proof_size=cfg.get_proof_size(),
            proof_quality=cfg.get_proof_quality(),
            skip_existing=not self._overwrite_cb.isChecked(),
            auto_bib_scan_enabled=self._bib_enabled.isChecked(),
            auto_bib_scan_backend=str(self._bib_backend.currentData()),
            auto_bib_min_confidence=self._bib_min_conf.value(),
            auto_bib_enforce_min_digits=self._bib_enforce_min_digits.isChecked(),
            auto_bib_min_digits=self._bib_min_digits.value(),
        )

        if self._config.auto_bib_scan_enabled:
            self._window.bibs_tab.ensure_csv()

        self._table.setRowCount(0)
        self._summary.clear()
        self._preview_label.setText("—")
        self._preview_name.clear()
        self._total = len(paths)
        self._start_time = time.monotonic()
        self._stop_requested = False
        self._progress.setMaximum(self._total)
        self._progress.setValue(0)
        self._progress.show()
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._info_label.clear()

        self._worker = ProcessWorker(
            paths, self._config,
            max_workers=cfg.get_worker_count() or None,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _stop(self) -> None:
        if self._worker and self._worker.isRunning():
            self._stop_requested = True
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

        if result.success and result.bib_candidates:
            photo_id = Path(result.source).stem
            self._window.bibs_tab.add_scanned_bibs(photo_id, result.bib_candidates)

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

        # ── Auto-deploy ──────────────────────────────────────────────────
        if (
            not self._stop_requested
            and errors == 0
            and self._auto_deploy_cb.isChecked()
        ):
            upload_workers = cfg.get_upload_worker_count() or None
            self._window.set_status("Auto-deploying to store…")
            self._deploy_worker = DeployWorker(
                upload_originals=True,
                upload_proofs=True,
                upload_bibs=False,
                max_workers=upload_workers,
                parent=self,
            )
            self._deploy_worker.log.connect(
                lambda msg: self._window.set_status(msg)
            )
            self._deploy_worker.finished.connect(self._on_auto_deploy_finished)
            self._deploy_worker.start()

    def _on_pattern_changed(self) -> None:
        single = self._wm_pattern.currentData() == "single-corner"
        self._wm_position.setEnabled(single)
        self._wm_angle.setEnabled(not single)
        self._wm_spacing_x.setEnabled(not single)
        self._wm_spacing_y.setEnabled(not single)

    def _save_watermark_settings(self) -> None:
        cfg.set_watermark_text(self._wm_text.text().strip())
        cfg.set_watermark_opacity(self._wm_opacity.value())
        cfg.set_watermark_pattern(str(self._wm_pattern.currentData()))
        cfg.set_watermark_position(str(self._wm_position.currentData()))
        cfg.set_watermark_angle(self._wm_angle.value())
        cfg.set_watermark_spacing_x_pct(self._wm_spacing_x.value())
        cfg.set_watermark_spacing_y_pct(self._wm_spacing_y.value())
        cfg.set_watermark_font_scale_pct(self._wm_font_scale.value())
        cfg.set_auto_bib_scan_enabled(self._bib_enabled.isChecked())
        cfg.set_auto_bib_scan_backend(str(self._bib_backend.currentData()))
        cfg.set_auto_bib_min_confidence(self._bib_min_conf.value())
        cfg.set_auto_bib_enforce_min_digits(self._bib_enforce_min_digits.isChecked())
        cfg.set_auto_bib_min_digits(self._bib_min_digits.value())

    def _on_bib_digits_toggle(self, checked: bool) -> None:
        self._bib_min_digits.setEnabled(checked)

    def _on_auto_deploy_finished(self, success: bool, message: str) -> None:
        self._window.set_status(f"Deploy: {message}")
        if self._deploy_worker:
            self._deploy_worker.deleteLater()
            self._deploy_worker = None
