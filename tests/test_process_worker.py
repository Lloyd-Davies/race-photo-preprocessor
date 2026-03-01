"""Tests for ProcessWorker QThread. Requires a running QApplication (pytest-qt)."""
from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.plugin import QtBot  # type: ignore[import]

from preprocessor.pipeline import ProcessConfig
from preprocessor.workers.process_worker import ProcessWorker


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_config(tmp_path: Path, slug: str = "test-event") -> ProcessConfig:
    return ProcessConfig(event_slug=slug, output_root=tmp_path)


def _wait_thread_stopped(worker: ProcessWorker) -> None:
    assert worker.wait(5_000), "worker thread did not stop in time"


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_finished_fires_with_all_results(
    qtbot: QtBot,
    photo_folder: Path,
    tmp_path: Path,
) -> None:
    """All JPEG files are processed and `finished` emits a result per file."""
    paths = [str(p) for p in sorted(photo_folder.glob("*.jpg"))]
    assert len(paths) == 3, "fixture should expose 3 JPEGs"

    worker = ProcessWorker(paths, _make_config(tmp_path))

    with qtbot.waitSignal(worker.finished, timeout=10_000) as blocker:
        worker.start()

    _wait_thread_stopped(worker)

    results = blocker.args[0]
    assert len(results) == 3
    assert all(r.success for r in results)
    assert all(not r.skipped for r in results)


def test_file_done_fires_for_each_file(
    qtbot: QtBot,
    photo_folder: Path,
    tmp_path: Path,
) -> None:
    """`file_done` is emitted once per file before `finished`."""
    paths = [str(p) for p in sorted(photo_folder.glob("*.jpg"))]

    worker = ProcessWorker(paths, _make_config(tmp_path))
    file_done_calls: list = []

    worker.file_done.connect(file_done_calls.append)

    with qtbot.waitSignal(worker.finished, timeout=10_000):
        worker.start()

    _wait_thread_stopped(worker)

    assert len(file_done_calls) == 3


def test_progress_emits_correct_indices(
    qtbot: QtBot,
    photo_folder: Path,
    tmp_path: Path,
) -> None:
    """`progress` carries 1-based current index, total, and path for each file."""
    paths = [str(p) for p in sorted(photo_folder.glob("*.jpg"))]

    worker = ProcessWorker(paths, _make_config(tmp_path))
    progress_calls: list[tuple[int, int, str]] = []

    worker.progress.connect(lambda cur, tot, p: progress_calls.append((cur, tot, p)))

    with qtbot.waitSignal(worker.finished, timeout=10_000):
        worker.start()

    _wait_thread_stopped(worker)

    assert len(progress_calls) == 3
    for idx, (cur, tot, path) in enumerate(progress_calls, start=1):
        assert cur == idx
        assert tot == 3
        assert path in paths


def test_error_result_for_missing_file(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    """A path that does not exist produces a failed ProcessResult."""
    missing = str(tmp_path / "nonexistent.jpg")
    worker = ProcessWorker([missing], _make_config(tmp_path))

    with qtbot.waitSignal(worker.finished, timeout=10_000) as blocker:
        worker.start()

    _wait_thread_stopped(worker)

    results = blocker.args[0]
    assert len(results) == 1
    assert results[0].success is False
    assert results[0].error is not None


def test_stop_halts_processing(
    qtbot: QtBot,
    photo_folder: Path,
    tmp_path: Path,
) -> None:
    """`stop()` causes the worker to finish early with fewer results."""
    # Use 3 files; stop() after first file_done → expect < 3 results in finished
    paths = [str(p) for p in sorted(photo_folder.glob("*.jpg"))]

    worker = ProcessWorker(paths, _make_config(tmp_path))

    # Stop after the very first file_done signal
    worker.file_done.connect(lambda _r: worker.stop())

    with qtbot.waitSignal(worker.finished, timeout=10_000) as blocker:
        worker.start()

    _wait_thread_stopped(worker)

    results = blocker.args[0]
    # At least 1 result (the file that triggered stop), but fewer than 3
    assert 1 <= len(results) < 3


def test_skip_existing(
    qtbot: QtBot,
    photo_folder: Path,
    tmp_path: Path,
) -> None:
    """Re-running with skip_existing=True marks already-copied files as skipped."""
    paths = [str(p) for p in sorted(photo_folder.glob("*.jpg"))]
    config = _make_config(tmp_path)

    # First run — no skips
    worker1 = ProcessWorker(paths, config)
    with qtbot.waitSignal(worker1.finished, timeout=10_000):
        worker1.start()
    _wait_thread_stopped(worker1)

    # Second run — all should be skipped
    worker2 = ProcessWorker(paths, config)
    with qtbot.waitSignal(worker2.finished, timeout=10_000) as blocker:
        worker2.start()

    _wait_thread_stopped(worker2)

    results = blocker.args[0]
    assert all(r.skipped for r in results)
