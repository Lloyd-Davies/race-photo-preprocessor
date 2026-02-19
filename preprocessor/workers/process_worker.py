"""Background worker for image processing pipeline."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from preprocessor.pipeline import ProcessConfig, ProcessResult, process_photo


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
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._paths = list(paths)
        self._config = config
        self._stop_requested = False

    # ── Public ────────────────────────────────────────────────────────────────

    def stop(self) -> None:
        """Request graceful cancellation (checked between files)."""
        self._stop_requested = True

    # ── QThread.run ──────────────────────────────────────────────────────────

    def run(self) -> None:
        results: list[ProcessResult] = []
        total = len(self._paths)

        for idx, path in enumerate(self._paths, start=1):
            if self._stop_requested:
                break

            self.progress.emit(idx, total, path)
            result = process_photo(path, self._config)
            results.append(result)
            self.file_done.emit(result)

        self.finished.emit(results)
