"""Deploy tab — store API upload."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import preprocessor.config as cfg
from preprocessor.workers.deploy_worker import DeployWorker

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from preprocessor.main_window import MainWindow


class DeployTab(QWidget):
    def __init__(self, parent: "MainWindow") -> None:
        super().__init__(parent)
        self._window = parent
        self._worker: DeployWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Output summary ────────────────────────────────────────────────────
        summary_group = QGroupBox("Output summary")
        summary_form = QFormLayout(summary_group)
        summary_form.setContentsMargins(10, 8, 10, 8)
        summary_form.setSpacing(8)
        summary_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self._originals_label = QLabel("—")
        self._originals_label.setProperty("hint", True)
        summary_form.addRow("Originals", self._originals_label)

        self._proofs_label = QLabel("—")
        self._proofs_label.setProperty("hint", True)
        summary_form.addRow("Proofs", self._proofs_label)

        self._bibs_label = QLabel("—")
        self._bibs_label.setProperty("hint", True)
        summary_form.addRow("Bib tags CSV", self._bibs_label)

        layout.addWidget(summary_group)

        # ── Upload options ────────────────────────────────────────────────────
        upload_group = QGroupBox("Upload to store")
        upload_layout = QVBoxLayout(upload_group)
        upload_layout.setContentsMargins(10, 8, 10, 8)
        upload_layout.setSpacing(6)

        self._cb_originals = QCheckBox("Upload originals")
        self._cb_originals.setChecked(True)
        self._cb_proofs = QCheckBox("Upload proofs")
        self._cb_proofs.setChecked(True)
        self._cb_bibs = QCheckBox("Upload bib tags")
        self._cb_bibs.setChecked(True)
        self._cb_replace_bibs = QCheckBox("Replace existing bib tags")
        self._cb_replace_bibs.setChecked(False)
        self._cb_replace_bibs.setToolTip(
            "When checked, all bib tags for this event are deleted from the store before uploading.\n"
            "Leave unchecked to add/update without removing existing tags."
        )
        self._cb_replace_bibs.setEnabled(self._cb_bibs.isChecked())
        self._cb_bibs.toggled.connect(self._cb_replace_bibs.setEnabled)

        upload_layout.addWidget(self._cb_originals)
        upload_layout.addWidget(self._cb_proofs)
        upload_layout.addWidget(self._cb_bibs)
        upload_layout.addWidget(self._cb_replace_bibs)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._upload_btn = QPushButton("Upload")
        self._upload_btn.setMinimumWidth(100)
        self._upload_btn.clicked.connect(self._on_upload)
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setProperty("secondary", True)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        self._connections_spin = QSpinBox()
        self._connections_spin.setRange(1, 16)
        self._connections_spin.setValue(cfg.get_upload_worker_count() or 4)
        self._connections_spin.setToolTip(
            "Number of simultaneous HTTP upload connections per batch.\n"
            "Higher = faster on fast connections; too high may overload the server."
        )
        self._connections_spin.setFixedWidth(60)
        self._connections_spin.valueChanged.connect(cfg.set_upload_worker_count)
        _conn_label = QLabel("Connections:")
        btn_row.addWidget(self._upload_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addSpacing(12)
        btn_row.addWidget(_conn_label)
        btn_row.addWidget(self._connections_spin)
        btn_row.addStretch()
        upload_layout.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setTextVisible(True)
        upload_layout.addWidget(self._progress)

        layout.addWidget(upload_group)

        # ── Log ───────────────────────────────────────────────────────────────
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(10, 8, 10, 8)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(160)
        self._log.setFont(self._log.font())
        log_layout.addWidget(self._log)
        layout.addWidget(log_group)

        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        self._refresh_summary()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._refresh_summary()

    # ── Summary ───────────────────────────────────────────────────────────────

    def _refresh_summary(self) -> None:
        slug = self._window.get_event_slug() if self._window else ""
        output_root = cfg.get_output_root().strip()

        if not slug or not output_root:
            self._originals_label.setText("Set event slug and output root in the sidebar")
            self._proofs_label.setText("—")
            self._bibs_label.setText("—")
            self._cb_originals.setText("Upload originals")
            self._cb_proofs.setText("Upload proofs")
            self._cb_bibs.setText("Upload bib tags")
            return

        root = Path(output_root)
        originals_dir = root / "originals" / slug
        proofs_dir = root / "proofs" / slug
        bibs_csv = root / "bibs" / slug / "bib_tags.csv"

        orig_count = len(list(originals_dir.glob("*.jpg"))) if originals_dir.exists() else 0
        proof_count = len(list(proofs_dir.glob("*.jpg"))) if proofs_dir.exists() else 0

        self._originals_label.setText(f"{orig_count} file(s)  —  {originals_dir}")
        self._proofs_label.setText(f"{proof_count} file(s)  —  {proofs_dir}")

        self._cb_originals.setText(f"Upload originals  ({orig_count} file(s))")
        self._cb_proofs.setText(f"Upload proofs  ({proof_count} file(s))")

        if bibs_csv.exists():
            lines = bibs_csv.read_text(encoding="utf-8").splitlines()
            tag_count = max(0, len(lines) - 1)
            self._bibs_label.setText(f"{tag_count} tag(s)  —  {bibs_csv}")
            self._cb_bibs.setText(f"Upload bib tags  ({tag_count} tag(s))")
        else:
            self._bibs_label.setText("Not generated yet — run OCR in the Bibs tab")
            self._cb_bibs.setText("Upload bib tags  (none)")

    # ── Upload ────────────────────────────────────────────────────────────────

    def _on_upload(self) -> None:
        if not self._cb_originals.isChecked() and not self._cb_proofs.isChecked() and not self._cb_bibs.isChecked():
            self._append_log("Nothing selected — tick at least one option.")
            return

        self._log.clear()
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._upload_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

        self._worker = DeployWorker(
            upload_originals=self._cb_originals.isChecked(),
            upload_proofs=self._cb_proofs.isChecked(),
            upload_bibs=self._cb_bibs.isChecked(),
            replace_bibs=self._cb_replace_bibs.isChecked(),
            max_workers=self._connections_spin.value(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self._append_log)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_stop(self) -> None:
        if self._worker:
            self._worker.stop()
        self._stop_btn.setEnabled(False)

    def _on_progress(self, current: int, total: int, label: str) -> None:
        if total > 0:
            self._progress.setMaximum(total)
            self._progress.setValue(current)
            self._progress.setFormat(f"{label}  ({current}/{total})")

    def _on_finished(self, ok: bool, message: str) -> None:
        self._upload_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._progress.setValue(self._progress.maximum())
        prefix = "✔" if ok else "✖"
        self._append_log(f"\n{prefix} {message}")

    def _append_log(self, text: str) -> None:
        self._log.appendPlainText(text)
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

