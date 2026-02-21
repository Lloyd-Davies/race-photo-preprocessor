"""Auto bib scanning scaffolding.

This module intentionally contains a minimal, no-op implementation that defines
stable interfaces for future OCR-based bib detection.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
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


def _extract_bib_parts(value: str) -> list[str]:
    parts = re.findall(r"\d+", value)
    if parts:
        return [_normalize_bib(part) for part in parts]
    normalized = _normalize_bib(value)
    return [normalized] if normalized else []


def _is_valid_bib(value: str, min_digits: int, enforce_min_digits: bool) -> bool:
    lower = max(1, min(5, int(min_digits))) if enforce_min_digits else 1
    return lower <= len(value) <= 5 and value.isdigit()


def scan_bibs_for_photo(photo_path: str, config: "ProcessConfig") -> list[BibDetection]:
    """Return bib detections for a processed proof image.

    Current behavior is intentionally no-op for scaffolding. Future
    implementation can branch on `config.auto_bib_scan_backend` and run OCR.
    """
    if not config.auto_bib_scan_enabled:
        return []

    min_conf = max(1, min(100, int(config.auto_bib_min_confidence))) / 100.0
    min_digits = max(1, min(5, int(config.auto_bib_min_digits)))
    enforce_min_digits = bool(config.auto_bib_enforce_min_digits)

    detections: list[BibDetection] = []
    seen: set[str] = set()
    candidates = extract_text_candidates(photo_path, backend=config.auto_bib_scan_backend)

    for candidate in candidates:
        if candidate.confidence < min_conf:
            continue

        bib_parts = _extract_bib_parts(candidate.text)
        for bib in bib_parts:
            if not _is_valid_bib(bib, min_digits=min_digits, enforce_min_digits=enforce_min_digits):
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
