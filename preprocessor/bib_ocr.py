"""OCR adapter scaffolding for bib scanning.

This module defines a backend-neutral interface that future OCR integrations can
implement without changing the pipeline contract.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OCRTextCandidate:
    text: str
    confidence: float
    bbox: tuple[int, int, int, int] | None = None


def extract_text_candidates(photo_path: str, backend: str = "none") -> list[OCRTextCandidate]:
    """Extract OCR text candidates from an image.

    Current scaffold behavior:
    - `none`: returns an empty list.
    - `ocr`: placeholder for a future OCR implementation, currently empty.
    - any other backend: returns empty list for safety.
    """
    _ = photo_path

    if backend in {"none", "ocr"}:
        return []

    return []
