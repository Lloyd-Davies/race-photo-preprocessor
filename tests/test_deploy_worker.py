"""Tests for DeployWorker QThread — upload order and skip logic."""
from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.plugin import QtBot  # type: ignore[import]

import preprocessor.config as cfg
import preprocessor.store_api as store_api
from preprocessor.workers.deploy_worker import DeployWorker


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_jpeg(path: Path) -> None:
    """Write a minimal valid JPEG (1×1 white pixel)."""
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1, 1), color=(255, 255, 255)).save(str(path), format="JPEG")


def _seed_event_files(root: Path, slug: str, ids: list[str]) -> None:
    """Create proof + original JPEG stubs for each photo id."""
    for pid in ids:
        _make_jpeg(root / "proofs" / slug / f"{pid}.jpg")
        _make_jpeg(root / "originals" / slug / f"{pid}.jpg")


def _patch_cfg(monkeypatch, tmp_path: Path, slug: str = "test-event") -> None:
    monkeypatch.setattr(cfg, "get_store_url", lambda: "http://fake-store")
    monkeypatch.setattr(cfg, "get_admin_credential", lambda: "testtoken")
    monkeypatch.setattr(cfg, "get_event_slug", lambda: slug)
    monkeypatch.setattr(cfg, "get_output_root", lambda: str(tmp_path))


def _wait_thread_stopped(worker: DeployWorker) -> None:
    assert worker.wait(5_000), "worker thread did not stop in time"


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_proofs_uploaded_before_originals(
    qtbot: QtBot,
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Proof files must be uploaded before their corresponding originals."""
    slug = "event-order"
    _patch_cfg(monkeypatch, tmp_path, slug)
    _seed_event_files(tmp_path, slug, ["img001", "img002"])

    monkeypatch.setattr(store_api, "find_event_id_by_slug", lambda *_: 1)
    monkeypatch.setattr(store_api, "get_uploaded_photo_ids", lambda *_: set())

    upload_calls: list[tuple[str, str]] = []  # (photo_id, kind)

    def fake_upload(_base_url, _token, _event_id, photo_id, kind, _path):
        upload_calls.append((photo_id, kind))
        return {}

    monkeypatch.setattr(store_api, "upload_photo", fake_upload)

    worker = DeployWorker(upload_originals=True, upload_proofs=True, upload_bibs=False)

    with qtbot.waitSignal(worker.finished, timeout=15_000) as blocker:
        worker.start()

    _wait_thread_stopped(worker)

    success, _ = blocker.args
    assert success, "Worker should finish successfully"

    kinds = [kind for _, kind in upload_calls]
    # All proof uploads must precede any original upload
    last_proof_idx = max((i for i, k in enumerate(kinds) if k == "proof"), default=-1)
    first_orig_idx = min((i for i, k in enumerate(kinds) if k == "original"), default=len(kinds))
    assert last_proof_idx < first_orig_idx, (
        f"Expected all proofs before originals; got order: {kinds}"
    )


def test_already_uploaded_photos_skipped(
    qtbot: QtBot,
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Photos whose stem is in get_uploaded_photo_ids are not re-uploaded."""
    slug = "event-skip"
    _patch_cfg(monkeypatch, tmp_path, slug)
    _seed_event_files(tmp_path, slug, ["img001", "img002", "img003"])

    monkeypatch.setattr(store_api, "find_event_id_by_slug", lambda *_: 2)
    # img001 and img002 are already on the server
    monkeypatch.setattr(store_api, "get_uploaded_photo_ids", lambda *_: {"img001", "img002"})

    upload_calls: list[str] = []

    def fake_upload(_base, _tok, _eid, photo_id, kind, _path):
        upload_calls.append(photo_id)
        return {}

    monkeypatch.setattr(store_api, "upload_photo", fake_upload)

    worker = DeployWorker(upload_originals=True, upload_proofs=True, upload_bibs=False)

    with qtbot.waitSignal(worker.finished, timeout=15_000) as blocker:
        worker.start()

    _wait_thread_stopped(worker)

    success, _ = blocker.args
    assert success

    # Only img003 should have been uploaded
    assert set(upload_calls) == {"img003"}
    assert "img001" not in upload_calls
    assert "img002" not in upload_calls


def test_deploy_worker_missing_store_url_aborts(
    qtbot: QtBot,
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Worker emits finished(False, ...) immediately when store URL is empty."""
    monkeypatch.setattr(cfg, "get_store_url", lambda: "")
    monkeypatch.setattr(cfg, "get_admin_credential", lambda: "tok")
    monkeypatch.setattr(cfg, "get_event_slug", lambda: "ev")
    monkeypatch.setattr(cfg, "get_output_root", lambda: str(tmp_path))

    worker = DeployWorker()

    with qtbot.waitSignal(worker.finished, timeout=5_000) as blocker:
        worker.start()

    _wait_thread_stopped(worker)

    success, message = blocker.args
    assert not success
    assert "URL" in message or "required" in message.lower()


def test_deploy_worker_missing_slug_aborts(
    qtbot: QtBot,
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Worker emits finished(False, ...) when event slug is empty."""
    monkeypatch.setattr(cfg, "get_store_url", lambda: "http://store")
    monkeypatch.setattr(cfg, "get_admin_credential", lambda: "tok")
    monkeypatch.setattr(cfg, "get_event_slug", lambda: "")
    monkeypatch.setattr(cfg, "get_output_root", lambda: str(tmp_path))

    worker = DeployWorker()

    with qtbot.waitSignal(worker.finished, timeout=5_000) as blocker:
        worker.start()

    _wait_thread_stopped(worker)

    success, message = blocker.args
    assert not success
    assert "slug" in message.lower()


def test_deploy_worker_event_not_found_aborts(
    qtbot: QtBot,
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Worker emits finished(False, ...) when event slug not found in the store."""
    _patch_cfg(monkeypatch, tmp_path)
    monkeypatch.setattr(store_api, "find_event_id_by_slug", lambda *_: None)

    worker = DeployWorker()

    with qtbot.waitSignal(worker.finished, timeout=5_000) as blocker:
        worker.start()

    _wait_thread_stopped(worker)

    success, message = blocker.args
    assert not success
    assert "not found" in message.lower()


def test_deploy_worker_nothing_to_upload_aborts(
    qtbot: QtBot,
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Worker emits finished(False, ...) when no files to upload exist."""
    _patch_cfg(monkeypatch, tmp_path, "empty-event")
    monkeypatch.setattr(store_api, "find_event_id_by_slug", lambda *_: 5)
    monkeypatch.setattr(store_api, "get_uploaded_photo_ids", lambda *_: set())

    # No files on disk → nothing to upload
    worker = DeployWorker(upload_originals=True, upload_proofs=True, upload_bibs=False)

    with qtbot.waitSignal(worker.finished, timeout=5_000) as blocker:
        worker.start()

    _wait_thread_stopped(worker)

    success, message = blocker.args
    assert not success
    assert "nothing" in message.lower()
