"""Background worker for bib OCR scanning."""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from preprocessor.bib_ocr import get_ocr_runtime_info
from preprocessor.bib_scan import scan_bibs_for_photo
from preprocessor.pipeline import ProcessConfig


class BibOcrWorker(QThread):
    """Runs OCR bib scanning in a background thread.

    Signals
    -------
    progress(current, total, filename)
        Emitted before each file is scanned.  current is 1-based.
    photo_done(photo_id, bibs, avg_confidence)
        Emitted for each file that produced at least one bib detection.
    finished(files_scanned, total_bibs)
        Emitted once when the run completes or is stopped.
    """

    progress: Signal = Signal(int, int, str)   # current (1-based), total, filename
    photo_done: Signal = Signal(str, list, float)  # photo_id, bibs, avg_confidence
    finished: Signal = Signal(int, int)             # files_with_hits, total_bibs

    def __init__(
        self,
        paths: list[str],
        config: ProcessConfig,
        max_workers: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._paths = list(paths)
        self._config = config
        self._max_workers = max_workers
        self._stop_requested = False

    def stop(self) -> None:
        self._stop_requested = True

    def _worker_count(self, total: int) -> int:
        if get_ocr_runtime_info(self._config.ocr_device).selected_device == "cuda":
            return 1
        if self._max_workers is not None and self._max_workers > 0:
            return min(self._max_workers, total)
        cpu = os.cpu_count() or 4
        return max(1, min(total, max(2, cpu - 1)))

    def run(self) -> None:
        total = len(self._paths)
        files_with_hits = 0
        total_bibs = 0

        if total == 0:
            self.finished.emit(0, 0)
            return

        n_workers = self._worker_count(total)

        if n_workers <= 1:
            # ── Serial path ───────────────────────────────────────────────────
            for idx, path in enumerate(self._paths, start=1):
                if self._stop_requested:
                    break
                self.progress.emit(idx, total, Path(path).name)
                try:
                    detections = scan_bibs_for_photo(path, self._config)
                except Exception:
                    continue
                if detections:
                    bibs = [d.bib for d in detections]
                    avg_conf = sum(d.confidence for d in detections) / len(detections)
                    files_with_hits += 1
                    total_bibs += len(bibs)
                    self.photo_done.emit(Path(path).stem, bibs, avg_conf)
        else:
            # ── Parallel path ─────────────────────────────────────────────────
            def _scan(p: str):
                return p, scan_bibs_for_photo(p, self._config)

            current = 0
            with ThreadPoolExecutor(max_workers=n_workers, thread_name_prefix="ocr") as ex:
                future_map = {ex.submit(_scan, p): p for p in self._paths}
                for future in as_completed(future_map):
                    current += 1
                    path = future_map[future]
                    self.progress.emit(current, total, Path(path).name)
                    if self._stop_requested:
                        for f in future_map:
                            f.cancel()
                        break
                    try:
                        _, detections = future.result()
                    except Exception:
                        continue
                    if detections:
                        bibs = [d.bib for d in detections]
                        avg_conf = sum(d.confidence for d in detections) / len(detections)
                        files_with_hits += 1
                        total_bibs += len(bibs)
                        self.photo_done.emit(Path(path).stem, bibs, avg_conf)

        self.finished.emit(files_with_hits, total_bibs)
