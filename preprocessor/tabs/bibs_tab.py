"""Bibs tab — bib scan review and upload."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING

import preprocessor.config as cfg
from preprocessor.bib_ocr import describe_ocr_runtime
from preprocessor.bib_results import bib_csv_path, ensure_bib_csv, load_bib_rows, merge_and_save_bibs
from preprocessor.pipeline import ProcessConfig
from preprocessor.store_api import (
    _user_error,
    find_event_id_by_slug,
    get_uploaded_photo_ids_strict,
    upload_bib_tags,
)
from preprocessor.workers.bib_ocr_worker import BibOcrWorker

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from preprocessor.main_window import MainWindow


class BibsTab(QWidget):
    def __init__(self, parent: "MainWindow") -> None:
        super().__init__(parent)
        self._window = parent
        self._ocr_worker: BibOcrWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # ── Toolbar ────────────────────────────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(8)

        self._load_btn = QPushButton("↺  Reload")
        self._load_btn.setFixedHeight(34)
        self._load_btn.clicked.connect(self.reload_from_disk)

        self._run_ocr_btn = QPushButton("▶  Run OCR")
        self._run_ocr_btn.setFixedHeight(34)
        self._run_ocr_btn.clicked.connect(self._start_ocr)

        self._stop_btn = QPushButton("⏹  Stop")
        self._stop_btn.setFixedHeight(34)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_ocr)

        self._remove_btn = QPushButton("Remove selected")
        self._remove_btn.setFixedHeight(34)
        self._remove_btn.setProperty("secondary", True)
        self._remove_btn.clicked.connect(self._remove_selected)

        self._upload_btn = QPushButton("↑  Upload to store")
        self._upload_btn.setFixedHeight(34)
        self._upload_btn.clicked.connect(self.upload_to_store)

        import os as _os
        _cpu = _os.cpu_count() or 8
        self._workers_spin = QSpinBox()
        self._workers_spin.setRange(0, _cpu)
        self._workers_spin.setValue(cfg.get_ocr_worker_count())
        self._workers_spin.setSpecialValueText("Auto")
        self._workers_spin.setToolTip(
            "Number of parallel threads for OCR scanning.\n"
            "'Auto' uses cpu_count−1.  Higher = faster but more CPU usage."
        )
        self._workers_spin.setFixedWidth(72)
        self._workers_spin.valueChanged.connect(cfg.set_ocr_worker_count)
        _workers_label = QLabel("Workers:")

        self._device_combo = QComboBox()
        self._device_combo.addItem("Auto", "auto")
        self._device_combo.addItem("CPU", "cpu")
        self._device_combo.addItem("CUDA", "cuda")
        device_idx = max(0, self._device_combo.findData(cfg.get_ocr_device()))
        self._device_combo.setCurrentIndex(device_idx)
        self._device_combo.currentIndexChanged.connect(self._on_device_changed)
        self._runtime_label = QLabel()
        self._runtime_label.setProperty("hint", True)
        self._on_device_changed()

        top.addWidget(self._load_btn)
        top.addWidget(self._run_ocr_btn)
        top.addWidget(self._stop_btn)
        top.addWidget(self._remove_btn)
        top.addSpacing(12)
        top.addWidget(_workers_label)
        top.addWidget(self._workers_spin)
        top.addWidget(QLabel("Device:"))
        top.addWidget(self._device_combo)
        top.addWidget(self._runtime_label)
        top.addStretch()
        top.addWidget(self._upload_btn)
        layout.addLayout(top)

        # ── Progress ────────────────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setFixedHeight(8)
        self._progress.setTextVisible(False)
        self._progress.hide()
        layout.addWidget(self._progress)

        self._scan_status = QLabel()
        self._scan_status.setProperty("hint", True)
        self._scan_status.hide()
        layout.addWidget(self._scan_status)

        # ── Results table ───────────────────────────────────────────────────────
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Photo ID", "Bib", "Confidence"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setDefaultSectionSize(22)
        layout.addWidget(self._table)

        self._status = QLabel("No scanned bibs loaded.")
        self._status.setProperty("hint", True)
        layout.addWidget(self._status)

        self.reload_from_disk()

    def _on_device_changed(self) -> None:
        device = str(self._device_combo.currentData())
        cfg.set_ocr_device(device)
        self._runtime_label.setText(describe_ocr_runtime(device))

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _event_slug(self) -> str:
        return self._window.get_event_slug().strip()

    def _csv_path(self) -> Path | None:
        slug = self._event_slug()
        output_root = cfg.get_output_root().strip()
        if not slug or not output_root:
            return None
        return bib_csv_path(Path(output_root), slug)

    def _load_rename_map(self, slug: str, output_root: str) -> dict[str, str]:
        """Return {original_filename_stem: photo_id} from _rename_map.csv, or {} if absent."""
        map_path = Path(output_root) / "originals" / slug / "_rename_map.csv"
        if not map_path.exists():
            return {}
        try:
            with map_path.open("r", encoding="utf-8", newline="") as f:
                return {
                    Path(row["original_name"]).stem: row["photo_id"]
                    for row in csv.DictReader(f)
                }
        except Exception:
            return {}

    def _resolve_scan_path(self, src: str, rename_map: dict[str, str] | None = None) -> str:
        """Return the best path to scan for bib OCR.

        Uses rename_map (original_stem → photo_id) to locate the correctly
        named original.  Falls back to the import source path if originals
        haven't been generated yet or the rename map is absent.
        """
        slug = self._event_slug()
        output_root = cfg.get_output_root().strip()
        if slug and output_root:
            stem = Path(src).stem
            photo_id = (rename_map or {}).get(stem, stem)
            original = Path(output_root) / "originals" / slug / f"{photo_id}.jpg"
            if original.exists():
                return str(original)
        return src

    # ── Public API used by ProcessTab ───────────────────────────────────────

    def add_scanned_bibs(self, photo_id: str, bibs: list[str], confidence: float = 1.0) -> None:
        """Merge bib detections into the CSV without a full table reload."""
        path = self._csv_path()
        if path is None:
            return
        ensure_bib_csv(path)
        merge_and_save_bibs(path, photo_id=photo_id, bibs=bibs, confidence=confidence)

    def ensure_csv(self) -> None:
        path = self._csv_path()
        if path is None:
            return
        ensure_bib_csv(path)

    # ── Table helpers ──────────────────────────────────────────────────────

    def reload_from_disk(self) -> None:
        path = self._csv_path()
        if path is None:
            self._table.setRowCount(0)
            self._status.setText("Set event slug and output root to load bib scan results.")
            return

        rows = load_bib_rows(path)
        self._table.setRowCount(0)
        for row in rows:
            idx = self._table.rowCount()
            self._table.insertRow(idx)
            self._table.setItem(idx, 0, QTableWidgetItem(row["photo_id"]))
            self._table.setItem(idx, 1, QTableWidgetItem(row["bib"]))
            self._table.setItem(idx, 2, QTableWidgetItem(row["confidence"]))

        self._status.setText(f"Loaded {len(rows)} bib tag(s) from {path.name}")

    def _collect_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for r in range(self._table.rowCount()):
            photo_id_item = self._table.item(r, 0)
            bib_item = self._table.item(r, 1)
            conf_item = self._table.item(r, 2)
            photo_id = photo_id_item.text().strip() if photo_id_item else ""
            bib = bib_item.text().strip() if bib_item else ""
            confidence = conf_item.text().strip() if conf_item else "1.0"
            if photo_id and bib:
                rows.append({"photo_id": photo_id, "bib": bib, "confidence": confidence or "1.0"})
        return rows

    def _save_rows(self, rows: list[dict[str, str]]) -> None:
        path = self._csv_path()
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["photo_id", "bib", "confidence"])
            writer.writeheader()
            writer.writerows(rows)

    def _save_current_table(self) -> None:
        self._save_rows(self._collect_rows())

    def _remap_rows_from_rename_map(
        self,
        rows: list[dict[str, str]],
        uploaded_photo_ids: set[str],
    ) -> tuple[list[dict[str, str]], int]:
        slug = self._event_slug()
        output_root = cfg.get_output_root().strip()
        if not slug or not output_root:
            return rows, 0

        rename_map = self._load_rename_map(slug, output_root)
        if not rename_map:
            return rows, 0

        remapped: list[dict[str, str]] = []
        changed = 0
        for row in rows:
            photo_id = row["photo_id"]
            mapped = rename_map.get(photo_id)
            if photo_id not in uploaded_photo_ids and mapped in uploaded_photo_ids:
                row = dict(row)
                row["photo_id"] = mapped
                changed += 1
            remapped.append(row)
        return remapped, changed

    def _missing_photo_id_message(self, missing: list[str]) -> str:
        preview = ", ".join(missing[:5])
        suffix = "" if len(missing) <= 5 else ", ..."
        return (
            f"Upload blocked: {len(missing)} photo ID(s) are not in the store for this event: "
            f"{preview}{suffix}. Upload/ingest photos first, then retry."
        )

    def _remove_selected(self) -> None:
        selected = sorted({idx.row() for idx in self._table.selectedIndexes()}, reverse=True)
        for row in selected:
            self._table.removeRow(row)
        self._save_current_table()
        self._status.setText(f"Removed {len(selected)} row(s).")

    # ── OCR worker ─────────────────────────────────────────────────────────

    def _start_ocr(self) -> None:
        if self._ocr_worker and self._ocr_worker.isRunning():
            return

        slug = self._event_slug()
        output_root = cfg.get_output_root().strip()
        if not slug or not output_root:
            self._status.setText("Event slug and output root are required.")
            return

        if cfg.get_auto_bib_scan_backend() == "none":
            self._status.setText("Set OCR backend to 'OCR (rapidocr)' in the Process tab first.")
            return
        import_paths = self._window.get_selected_images() or self._window.import_tab.all_paths()
        if not import_paths:
            self._status.setText("No images available — import some in the Import tab first.")
            return

        # Load rename map so scan paths use the renamed photo_id filenames,
        # not the original camera names.  Falls back gracefully if absent.
        rename_map = self._load_rename_map(slug, output_root)
        scan_paths = [self._resolve_scan_path(p, rename_map) for p in import_paths]

        config = ProcessConfig(
            event_slug=slug,
            output_root=Path(output_root),
            auto_bib_scan_enabled=True,
            auto_bib_scan_backend=cfg.get_auto_bib_scan_backend(),
            ocr_device=str(self._device_combo.currentData()),
            auto_bib_min_confidence=cfg.get_auto_bib_min_confidence(),
            auto_bib_enforce_min_digits=cfg.get_auto_bib_enforce_min_digits(),
            auto_bib_min_digits=cfg.get_auto_bib_min_digits(),
        )

        self.ensure_csv()

        self._progress.setMaximum(len(scan_paths))
        self._progress.setValue(0)
        self._progress.show()
        self._scan_status.show()
        self._run_ocr_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status.setText("")

        self._ocr_worker = BibOcrWorker(
            scan_paths, config,
            max_workers=self._workers_spin.value() or None,
        )
        self._ocr_worker.progress.connect(self._on_ocr_progress)
        self._ocr_worker.photo_done.connect(self._on_photo_done)
        self._ocr_worker.finished.connect(self._on_ocr_finished)
        self._ocr_worker.start()

    def _stop_ocr(self) -> None:
        if self._ocr_worker and self._ocr_worker.isRunning():
            self._stop_btn.setEnabled(False)
            self._ocr_worker.stop()

    def _on_ocr_progress(self, current: int, total: int, filename: str) -> None:
        self._progress.setValue(current - 1)
        self._scan_status.setText(f"Scanning {current}/{total}: {filename}")

    def _on_photo_done(self, photo_id: str, bibs: list[str], confidence: float) -> None:
        # Persist immediately; single table reload happens in _on_ocr_finished
        self.add_scanned_bibs(photo_id, bibs, confidence)

    def _on_ocr_finished(self, files_with_hits: int, total_bibs: int) -> None:
        self._progress.hide()
        self._scan_status.hide()
        self._run_ocr_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

        if self._ocr_worker:
            self._ocr_worker.deleteLater()
            self._ocr_worker = None

        self.reload_from_disk()
        self._status.setText(
            f"Scan complete — {files_with_hits} file(s) with bibs detected, {total_bibs} total bib tag(s)."
        )
        self._window.set_status(f"Bib OCR complete: {total_bibs} tag(s) found in {files_with_hits} file(s).")

    # ── Upload ───────────────────────────────────────────────────────────────

    def upload_to_store(self) -> None:
        slug = self._event_slug()
        base_url = cfg.get_store_url().strip()
        token = cfg.get_store_token().strip()

        if not slug:
            self._status.setText("Event slug is required to upload bib tags.")
            return
        if not base_url or not token:
            self._status.setText("Store URL and admin token are required.")
            return

        rows = self._collect_rows()
        if not rows:
            self._status.setText("No bib rows to upload.")
            return

        event_id = find_event_id_by_slug(base_url, token, slug)
        if event_id is None:
            self._status.setText(f"Could not find event '{slug}' on store API.")
            return

        try:
            uploaded_photo_ids = get_uploaded_photo_ids_strict(base_url, token, event_id)
        except Exception as exc:
            self._status.setText(f"Upload failed: {_user_error(exc)}")
            return

        rows, remapped = self._remap_rows_from_rename_map(rows, uploaded_photo_ids)
        if remapped:
            self._save_rows(rows)
            self.reload_from_disk()

        missing = sorted({row["photo_id"] for row in rows} - uploaded_photo_ids)
        if missing:
            self._status.setText(self._missing_photo_id_message(missing))
            return

        payload = []
        for row in rows:
            try:
                conf = float(row["confidence"])
            except Exception:
                conf = 1.0
            payload.append({"photo_id": row["photo_id"], "bib": row["bib"], "confidence": conf})

        try:
            result = upload_bib_tags(base_url, token, event_id=event_id, tags=payload)
            added = int(result.get("added", 0))
            prefix = f"Remapped {remapped} bib row(s). " if remapped else ""
            self._status.setText(f"{prefix}Uploaded. Added {added} new bib tag(s).")
        except Exception as exc:
            self._status.setText(f"Upload failed: {_user_error(exc)}")
