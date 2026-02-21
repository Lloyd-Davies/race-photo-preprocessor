from __future__ import annotations

from pathlib import Path

from preprocessor.bib_results import bib_csv_path, load_bib_rows, merge_and_save_bibs


def test_merge_and_load_bib_rows(tmp_path: Path) -> None:
    path = bib_csv_path(tmp_path, "my-event")

    merge_and_save_bibs(path, photo_id="IMG_001", bibs=["465", "469"], confidence=0.9)
    merge_and_save_bibs(path, photo_id="IMG_001", bibs=["465"], confidence=0.9)  # duplicate ignored
    merge_and_save_bibs(path, photo_id="IMG_002", bibs=["423"], confidence=0.8)

    rows = load_bib_rows(path)
    assert rows == [
        {"photo_id": "IMG_001", "bib": "465", "confidence": "0.900"},
        {"photo_id": "IMG_001", "bib": "469", "confidence": "0.900"},
        {"photo_id": "IMG_002", "bib": "423", "confidence": "0.800"},
    ]
