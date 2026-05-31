from __future__ import annotations

import csv
from pathlib import Path

from pytestqt.plugin import QtBot  # type: ignore[import]

import preprocessor.config as cfg
from preprocessor.bib_results import load_bib_rows
from preprocessor.main_window import MainWindow
from preprocessor.tabs import bibs_tab as bibs_module


def _window(qtbot: QtBot, tmp_path: Path, slug: str = "race-a") -> MainWindow:
    cfg.set_event_slug(slug)
    cfg.set_event_name("Race A")
    cfg.set_output_root(str(tmp_path))
    cfg.set_store_url("http://store.local")
    cfg.set_store_token("secret")
    window = MainWindow(dark_mode=True)
    qtbot.addWidget(window)
    return window


def _write_bib_csv(root: Path, slug: str, rows: list[dict[str, str]]) -> Path:
    path = root / "bibs" / slug / "bib_tags.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["photo_id", "bib", "confidence"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_rename_map(root: Path, slug: str) -> None:
    path = root / "originals" / slug / "_rename_map.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["original_name", "photo_id"])
        writer.writeheader()
        writer.writerow({"original_name": "DSC_001.jpg", "photo_id": "race-a-0001"})


def test_bibs_upload_remaps_camera_stems_before_upload(
    monkeypatch,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    slug = "race-a"
    csv_path = _write_bib_csv(
        tmp_path,
        slug,
        [{"photo_id": "DSC_001", "bib": "42", "confidence": "0.900"}],
    )
    _write_rename_map(tmp_path, slug)
    window = _window(qtbot, tmp_path, slug)
    window.bibs_tab.reload_from_disk()

    uploaded: list[list[dict[str, object]]] = []
    monkeypatch.setattr(bibs_module, "find_event_id_by_slug", lambda *_args: 11)
    monkeypatch.setattr(bibs_module, "get_uploaded_photo_ids_strict", lambda *_args: {"race-a-0001"})
    monkeypatch.setattr(
        bibs_module,
        "upload_bib_tags",
        lambda *_args, tags, **_kwargs: uploaded.append(tags) or {"added": 1},
    )

    window.bibs_tab.upload_to_store()

    assert uploaded
    assert uploaded[0][0]["photo_id"] == "race-a-0001"
    assert load_bib_rows(csv_path)[0]["photo_id"] == "race-a-0001"
    assert "Remapped 1" in window.bibs_tab._status.text()
    assert "Uploaded" in window.bibs_tab._status.text()


def test_bibs_upload_blocks_missing_photo_ids(
    monkeypatch,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    slug = "race-a"
    _write_bib_csv(
        tmp_path,
        slug,
        [{"photo_id": "missing-photo", "bib": "42", "confidence": "0.900"}],
    )
    window = _window(qtbot, tmp_path, slug)
    window.bibs_tab.reload_from_disk()

    monkeypatch.setattr(bibs_module, "find_event_id_by_slug", lambda *_args: 11)
    monkeypatch.setattr(bibs_module, "get_uploaded_photo_ids_strict", lambda *_args: {"race-a-0001"})

    def fail_upload(*_args, **_kwargs):
        raise AssertionError("upload_bib_tags should not be called for missing photo IDs")

    monkeypatch.setattr(bibs_module, "upload_bib_tags", fail_upload)

    window.bibs_tab.upload_to_store()

    message = window.bibs_tab._status.text()
    assert "Upload blocked" in message
    assert "missing-photo" in message
    assert "Upload/ingest photos first" in message
