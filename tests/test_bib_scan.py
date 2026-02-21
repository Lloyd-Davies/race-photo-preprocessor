from __future__ import annotations

from pathlib import Path

import pytest

from preprocessor.bib_ocr import OCRTextCandidate
from preprocessor.pipeline import ProcessConfig
from preprocessor.bib_scan import scan_bibs_for_photo


def test_scan_bibs_disabled_returns_empty(tmp_path: Path) -> None:
    config = ProcessConfig(event_slug="ev", output_root=tmp_path, auto_bib_scan_enabled=False)
    assert scan_bibs_for_photo("dummy.jpg", config) == []


def test_scan_bibs_filters_and_normalizes(monkeypatch, tmp_path: Path) -> None:
    def _fake_extract(_photo_path: str, backend: str = "none") -> list[OCRTextCandidate]:
        assert backend == "ocr"
        return [
            OCRTextCandidate(text="BIB 123", confidence=0.95),
            OCRTextCandidate(text="123", confidence=0.99),  # duplicate after normalize
            OCRTextCandidate(text="A-7", confidence=0.90),
            OCRTextCandidate(text="999999", confidence=0.99),  # too long
            OCRTextCandidate(text="42", confidence=0.40),  # below threshold
        ]

    monkeypatch.setattr("preprocessor.bib_scan.extract_text_candidates", _fake_extract)

    config = ProcessConfig(
        event_slug="ev",
        output_root=tmp_path,
        auto_bib_scan_enabled=True,
        auto_bib_scan_backend="ocr",
        auto_bib_min_confidence=70,
        auto_bib_enforce_min_digits=True,
        auto_bib_min_digits=3,
    )

    results = scan_bibs_for_photo("dummy.jpg", config)
    bibs = [d.bib for d in results]

    assert bibs == ["123"]


def test_scan_bibs_extracts_multiple_numbers_from_single_candidate(monkeypatch, tmp_path: Path) -> None:
    def _fake_extract(_photo_path: str, backend: str = "none") -> list[OCRTextCandidate]:
        assert backend == "ocr"
        return [
            OCRTextCandidate(text="1234 567", confidence=0.95),
            OCRTextCandidate(text="bib: 567", confidence=0.90),
        ]

    monkeypatch.setattr("preprocessor.bib_scan.extract_text_candidates", _fake_extract)

    config = ProcessConfig(
        event_slug="ev",
        output_root=tmp_path,
        auto_bib_scan_enabled=True,
        auto_bib_scan_backend="ocr",
        auto_bib_min_confidence=60,
    )

    results = scan_bibs_for_photo("dummy.jpg", config)
    bibs = [d.bib for d in results]

    assert bibs == ["1234", "567"]


def test_scan_bibs_allows_short_bibs_when_min_digits_not_enforced(monkeypatch, tmp_path: Path) -> None:
    def _fake_extract(_photo_path: str, backend: str = "none") -> list[OCRTextCandidate]:
        assert backend == "ocr"
        return [
            OCRTextCandidate(text="18", confidence=0.95),
            OCRTextCandidate(text="42", confidence=0.90),
        ]

    monkeypatch.setattr("preprocessor.bib_scan.extract_text_candidates", _fake_extract)

    config = ProcessConfig(
        event_slug="ev",
        output_root=tmp_path,
        auto_bib_scan_enabled=True,
        auto_bib_scan_backend="ocr",
        auto_bib_min_confidence=60,
        auto_bib_enforce_min_digits=False,
        auto_bib_min_digits=3,
    )

    results = scan_bibs_for_photo("dummy.jpg", config)
    bibs = [d.bib for d in results]

    assert bibs == ["18", "42"]


def test_scan_bibs_unknown_backend_safe_noop(tmp_path: Path) -> None:
    config = ProcessConfig(
        event_slug="ev",
        output_root=tmp_path,
        auto_bib_scan_enabled=True,
        auto_bib_scan_backend="unsupported",
        auto_bib_min_confidence=1,
    )
    assert scan_bibs_for_photo("dummy.jpg", config) == []


def test_scan_bibs_ocr_multi_numbers_single_photo(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    cv2 = pytest.importorskip("cv2")
    pytest.importorskip("rapidocr_onnxruntime")

    photo = tmp_path / "multi-bib.jpg"
    img = np.full((1000, 1800, 3), 255, np.uint8)
    cv2.putText(img, "1234", (180, 360), cv2.FONT_HERSHEY_SIMPLEX, 5, (0, 0, 0), 10, cv2.LINE_AA)
    cv2.putText(img, "567", (980, 760), cv2.FONT_HERSHEY_SIMPLEX, 5, (0, 0, 0), 10, cv2.LINE_AA)
    cv2.imwrite(str(photo), img)

    config = ProcessConfig(
        event_slug="ev",
        output_root=tmp_path,
        auto_bib_scan_enabled=True,
        auto_bib_scan_backend="ocr",
        auto_bib_min_confidence=60,
    )

    results = scan_bibs_for_photo(str(photo), config)
    bibs = {d.bib for d in results}
    assert "1234" in bibs
    assert "567" in bibs
