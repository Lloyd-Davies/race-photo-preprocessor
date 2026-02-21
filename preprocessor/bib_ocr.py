"""OCR adapter scaffolding for bib scanning.

This module defines a backend-neutral interface that future OCR integrations can
implement without changing the pipeline contract.
"""
from __future__ import annotations

from dataclasses import dataclass

_RAPID_OCR_ENGINE = None


@dataclass
class OCRTextCandidate:
    text: str
    confidence: float
    bbox: tuple[int, int, int, int] | None = None


def extract_text_candidates(photo_path: str, backend: str = "none") -> list[OCRTextCandidate]:
    """Extract OCR text candidates from an image.

    Current behavior:
    - `none`: returns an empty list.
    - `ocr`: uses `rapidocr-onnxruntime` when available.
    - any other backend: returns empty list for safety.
    """
    global _RAPID_OCR_ENGINE

    if backend == "none":
        return []

    if backend != "ocr":
        return []

    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore[import-not-found]
    except Exception:
        return []

    if _RAPID_OCR_ENGINE is None:
        _RAPID_OCR_ENGINE = RapidOCR()

    result, _elapsed = _RAPID_OCR_ENGINE(photo_path)
    if not result:
        return []

    out: list[OCRTextCandidate] = []
    for item in result:
        if len(item) < 3:
            continue

        poly = item[0]
        text = str(item[1])
        confidence = float(item[2])

        bbox = None
        try:
            xs = [int(p[0]) for p in poly]
            ys = [int(p[1]) for p in poly]
            bbox = (min(xs), min(ys), max(xs), max(ys))
        except Exception:
            bbox = None

        out.append(OCRTextCandidate(text=text, confidence=confidence, bbox=bbox))

    return out
