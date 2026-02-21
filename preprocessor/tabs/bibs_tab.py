"""Bibs tab — bib scan review and upload."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import preprocessor.config as cfg
from preprocessor.bib_results import bib_csv_path, ensure_bib_csv, load_bib_rows, merge_and_save_bibs
from preprocessor.bib_scan import scan_bibs_for_photo
from preprocessor.pipeline import ProcessConfig
from preprocessor.store_api import find_event_id_by_slug, upload_bib_tags

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        top = QHBoxLayout()
        self._load_btn = QPushButton("Reload scanned bibs")
        self._load_btn.clicked.connect(self.reload_from_disk)
        self._remove_btn = QPushButton("Remove selected")
        self._remove_btn.setProperty("secondary", True)
        self._remove_btn.clicked.connect(self._remove_selected)
        self._run_ocr_btn = QPushButton("Run OCR on selected")
        self._run_ocr_btn.setProperty("secondary", True)
        self._run_ocr_btn.clicked.connect(self.run_ocr_scan)
        self._upload_btn = QPushButton("Upload bib tags to store")
        self._upload_btn.clicked.connect(self.upload_to_store)
        top.addWidget(self._load_btn)
        top.addWidget(self._remove_btn)
        top.addWidget(self._run_ocr_btn)
        top.addStretch()
        top.addWidget(self._upload_btn)
        layout.addLayout(top)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Photo ID", "Bib", "Confidence"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        layout.addWidget(self._table)

        self._status = QLabel("No scanned bibs loaded.")
        self._status.setProperty("hint", True)
        layout.addWidget(self._status)

        self.reload_from_disk()

    def _event_slug(self) -> str:
        return self._window.get_event_slug().strip()

    def _csv_path(self) -> Path | None:
        slug = self._event_slug()
        output_root = cfg.get_output_root().strip()
        if not slug or not output_root:
            return None
        return bib_csv_path(Path(output_root), slug)

    def add_scanned_bibs(self, photo_id: str, bibs: list[str]) -> None:
        path = self._csv_path()
        if path is None:
            return
        ensure_bib_csv(path)
        merge_and_save_bibs(path, photo_id=photo_id, bibs=bibs, confidence=1.0)
        self.reload_from_disk()

    def ensure_csv(self) -> None:
        path = self._csv_path()
        if path is None:
            return
        ensure_bib_csv(path)
        self.reload_from_disk()

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

        self._status.setText(f"Loaded {len(rows)} bib tags from {path.name}")

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

    def _save_current_table(self) -> None:
        path = self._csv_path()
        if path is None:
            return

        rows = self._collect_rows()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as f:
            import csv

            writer = csv.DictWriter(f, fieldnames=["photo_id", "bib", "confidence"])
            writer.writeheader()
            writer.writerows(rows)

    def _remove_selected(self) -> None:
        selected = sorted({idx.row() for idx in self._table.selectedIndexes()}, reverse=True)
        for row in selected:
            self._table.removeRow(row)
        self._save_current_table()
        self._status.setText(f"Removed {len(selected)} rows.")

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

        payload = []
        for row in rows:
            try:
                conf = float(row["confidence"])
            except Exception:
                conf = 1.0
            payload.append({
                "photo_id": row["photo_id"],
                "bib": row["bib"],
                "confidence": conf,
            })

        try:
            result = upload_bib_tags(base_url, token, event_id=event_id, tags=payload)
            added = int(result.get("added", 0))
            self._status.setText(f"Uploaded bib tags. Added {added} new tags.")
        except Exception as exc:
            self._status.setText(f"Upload failed: {exc}")

    def run_ocr_scan(self) -> None:
        slug = self._event_slug()
        output_root = cfg.get_output_root().strip()
        if not slug or not output_root:
            self._status.setText("Event slug and output root are required.")
            return

        selected = self._window.get_selected_images()
        paths = selected if selected else self._window.import_tab.all_paths()
        if not paths:
            self._status.setText("No images available to scan. Use Import tab first.")
            return

        config = ProcessConfig(
            event_slug=slug,
            output_root=Path(output_root),
            auto_bib_scan_enabled=True,
            auto_bib_scan_backend=cfg.get_auto_bib_scan_backend(),
            auto_bib_min_confidence=cfg.get_auto_bib_min_confidence(),
            auto_bib_min_digits=cfg.get_auto_bib_min_digits(),
        )

        self.ensure_csv()

        files_with_hits = 0
        total_hits = 0
        for src in paths:
            photo_id = Path(src).stem
            detections = scan_bibs_for_photo(src, config)
            bibs = [d.bib for d in detections]
            if bibs:
                files_with_hits += 1
                total_hits += len(bibs)
                self.add_scanned_bibs(photo_id, bibs)

        self.reload_from_disk()
        self._status.setText(
            f"OCR complete: {files_with_hits}/{len(paths)} files with bibs, {total_hits} detections."
        )
