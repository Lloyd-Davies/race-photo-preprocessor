"""OCR adapter for bib scanning.

Backend-neutral interface — currently supports `none` (no-op) and `ocr` (RapidOCR).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

_RAPID_OCR_ENGINE = None
_OCR_LOCK = threading.Lock()


@dataclass
class OCRTextCandidate:
    text: str
    confidence: float
    bbox: tuple[int, int, int, int] | None = None


def extract_text_candidates(photo_path: str, backend: str = "none") -> list[OCRTextCandidate]:
    """Extract OCR text candidates from an image.

    - ``none``: returns an empty list (no-op).
    - ``ocr``: uses ``rapidocr-onnxruntime`` when available.
    - any other value: safe no-op.
    """
    global _RAPID_OCR_ENGINE

    if backend not in ("ocr",):
        return []

    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore[import-not-found]
    except Exception:
        return []

    if _RAPID_OCR_ENGINE is None:
        _RAPID_OCR_ENGINE = RapidOCR()

    with _OCR_LOCK:
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

        bbox: tuple[int, int, int, int] | None = None
        try:
            xs = [int(p[0]) for p in poly]
            ys = [int(p[1]) for p in poly]
            bbox = (min(xs), min(ys), max(xs), max(ys))
        except Exception:
            pass

        out.append(OCRTextCandidate(text=text, confidence=confidence, bbox=bbox))

    return out
