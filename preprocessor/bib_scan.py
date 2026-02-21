"""Auto bib scanning scaffolding.

This module intentionally contains a minimal, no-op implementation that defines
stable interfaces for future OCR-based bib detection.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from preprocessor.bib_ocr import extract_text_candidates

if TYPE_CHECKING:
    from preprocessor.pipeline import ProcessConfig


@dataclass
class BibDetection:
    bib: str
    confidence: float
    bbox: tuple[int, int, int, int] | None = None


def _normalize_bib(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def _is_valid_bib(value: str) -> bool:
    # Keep simple and conservative for now: 1-5 digit numeric bibs.
    return 1 <= len(value) <= 5 and value.isdigit()


def scan_bibs_for_photo(photo_path: str, config: "ProcessConfig") -> list[BibDetection]:
    """Return bib detections for a processed proof image.

    Current behavior is intentionally no-op for scaffolding. Future
    implementation can branch on `config.auto_bib_scan_backend` and run OCR.
    """
    if not config.auto_bib_scan_enabled:
        return []

    min_conf = max(1, min(100, int(config.auto_bib_min_confidence))) / 100.0

    detections: list[BibDetection] = []
    seen: set[str] = set()
    candidates = extract_text_candidates(photo_path, backend=config.auto_bib_scan_backend)

    for candidate in candidates:
        if candidate.confidence < min_conf:
            continue

        bib = _normalize_bib(candidate.text)
        if not _is_valid_bib(bib):
            continue
        if bib in seen:
            continue

        detections.append(
            BibDetection(
                bib=bib,
                confidence=candidate.confidence,
                bbox=candidate.bbox,
            )
        )
        seen.add(bib)

    return detections
