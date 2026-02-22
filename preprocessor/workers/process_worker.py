"""Background worker for image processing pipeline."""
from __future__ import annotations

import os
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from preprocessor.pipeline import ProcessConfig, ProcessResult, process_photo
from preprocessor.rename import build_rename_plan, write_rename_map


class ProcessWorker(QThread):
    """
    Runs the processing pipeline in a background thread.

    Signals
    -------
    progress(current, total, path)
        Emitted before each file begins.  current is 1-based.
    file_done(result)
        Emitted after each file completes.
    finished(results)
        Emitted once when the run completes or is stopped.
    """

    progress: Signal = Signal(int, int, str)   # current (1-based), total, path
    file_done: Signal = Signal(object)          # ProcessResult
    finished: Signal = Signal(list)             # list[ProcessResult]

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

    # ── Public ────────────────────────────────────────────────────────────────

    def stop(self) -> None:
        """Request graceful cancellation (checked between files)."""
        self._stop_requested = True

    def _recommended_workers(self, total: int) -> int:
        if self._max_workers is not None and self._max_workers > 0:
            return min(self._max_workers, total)
        if total <= 1:
            return 1
        cpu = os.cpu_count() or 4
        # Keep one core free for UI/system responsiveness.
        return max(1, min(total, max(2, cpu - 1)))

    # ── QThread.run ──────────────────────────────────────────────────────────

    def run(self) -> None:
        results: list[ProcessResult] = []
        total = len(self._paths)

        if total == 0:
            self.finished.emit(results)
            return

        # Build rename plan (natural-sorted) and write the mapping CSV before
        # any processing begins so the map is always present even if cancelled.
        plan = build_rename_plan([Path(p) for p in self._paths], self._config.event_slug)
        map_csv = (
            self._config.output_root
            / "originals"
            / self._config.event_slug
            / "_rename_map.csv"
        )
        write_rename_map(plan, map_csv)

        max_workers = self._recommended_workers(total)

        if max_workers <= 1:
            for idx, (path, photo_id) in enumerate(plan, start=1):
                if self._stop_requested:
                    break

                self.progress.emit(idx, total, str(path))
                result = process_photo(str(path), self._config, photo_id)
                results.append(result)
                self.file_done.emit(result)

            self.finished.emit(results)
            return

        executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="process")
        futures: dict[Future[ProcessResult], tuple[int, str, str]] = {}
        submitted = 0

        def submit_next() -> bool:
            nonlocal submitted
            if self._stop_requested:
                return False
            if submitted >= total:
                return False

            path, photo_id = plan[submitted]
            submitted += 1
            self.progress.emit(submitted, total, str(path))

            future = executor.submit(process_photo, str(path), self._config, photo_id)
            futures[future] = (submitted, str(path), photo_id)
            return True

        try:
            for _ in range(min(max_workers, total)):
                if not submit_next():
                    break

            while futures:
                done, _pending = wait(list(futures.keys()), return_when=FIRST_COMPLETED)

                for future in done:
                    _idx, path, _pid = futures.pop(future)
                    if self._stop_requested:
                        continue

                    try:
                        result = future.result()
                    except Exception as exc:  # defensive: capture worker exceptions
                        result = ProcessResult(source=path, success=False, error=str(exc))

                    results.append(result)
                    self.file_done.emit(result)

                    if self._stop_requested:
                        break

                    submit_next()

                if self._stop_requested:
                    for pending_future in futures:
                        pending_future.cancel()
                    break

        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        self.finished.emit(results)
