from __future__ import annotations

from pathlib import Path

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
    )

    results = scan_bibs_for_photo("dummy.jpg", config)
    bibs = [d.bib for d in results]

    assert bibs == ["123", "7"]


def test_scan_bibs_unknown_backend_safe_noop(tmp_path: Path) -> None:
    config = ProcessConfig(
        event_slug="ev",
        output_root=tmp_path,
        auto_bib_scan_enabled=True,
        auto_bib_scan_backend="unsupported",
        auto_bib_min_confidence=1,
    )
    assert scan_bibs_for_photo("dummy.jpg", config) == []
