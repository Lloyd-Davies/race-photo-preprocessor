"""Image processing pipeline — pure functions, no Qt. (Phase 3)"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from preprocessor.bib_scan import scan_bibs_for_photo


@dataclass
class ProcessConfig:
    event_slug: str
    output_root: Path
    watermark_text: str = "© Race Photos"
    watermark_opacity: int = 85          # 0-100
    watermark_pattern: str = "diagonal-repeat"
    watermark_position: str = "bottom-right"
    watermark_angle: int = -32
    watermark_spacing_x_pct: int = 22
    watermark_spacing_y_pct: int = 16
    watermark_font_scale_pct: int = 100
    proof_size: int = 1600               # longest edge px
    proof_quality: int = 82              # JPEG quality
    skip_existing: bool = True
    watermark_logo_path: str | None = None
    watermark_logo_opacity: int = 15     # 0-100
    auto_bib_scan_enabled: bool = False
    auto_bib_scan_backend: str = "none"
    auto_bib_min_confidence: int = 70
    auto_bib_enforce_min_digits: bool = False
    auto_bib_min_digits: int = 3


@dataclass
class ProcessResult:
    source: str
    success: bool
    skipped: bool = False
    error: str | None = None
    bib_candidates: list[str] = field(default_factory=list)


_EXIF_TIME_TAGS = {
    0x0132,  # DateTime
    0x9003,  # DateTimeOriginal
    0x9004,  # DateTimeDigitized
    0x9010,  # OffsetTime
    0x9011,  # OffsetTimeOriginal
    0x9012,  # OffsetTimeDigitized
    0x9290,  # SubSecTime
    0x9291,  # SubSecTimeOriginal
    0x9292,  # SubSecTimeDigitized
}


def _extract_time_exif_bytes(source_img) -> bytes | None:
    exif = source_img.getexif()
    if not exif:
        return None

    from PIL import Image

    keep = Image.Exif()
    for tag in _EXIF_TIME_TAGS:
        if tag in exif:
            keep[tag] = exif[tag]

    return keep.tobytes() if len(keep) > 0 else None


def process_photo(source: str, config: ProcessConfig) -> ProcessResult:
    """
    Process a single photo: copy as original, generate resized/watermarked proof.

    Original: pixel-perfect copy, EXIF preserved.
    Proof: resized to longest edge ≤ proof_size, watermark applied, capture-time EXIF preserved.
    """
    import shutil

    source_path = Path(source)
    if not source_path.exists():
        return ProcessResult(source=source, success=False, error="File not found")

    photo_id = source_path.stem
    proofs_dir = config.output_root / "proofs" / config.event_slug
    originals_dir = config.output_root / "originals" / config.event_slug
    proofs_dir.mkdir(parents=True, exist_ok=True)
    originals_dir.mkdir(parents=True, exist_ok=True)

    original_dest = originals_dir / f"{photo_id}.jpg"
    proof_dest = proofs_dir / f"{photo_id}.jpg"

    if config.skip_existing and original_dest.exists() and proof_dest.exists():
        bib_candidates: list[str] = []
        if config.auto_bib_scan_enabled:
            detections = scan_bibs_for_photo(str(proof_dest), config)
            bib_candidates = [d.bib for d in detections]
        return ProcessResult(source=source, success=True, skipped=True, bib_candidates=bib_candidates)

    try:
        # Original: preserved as pixel-perfect copy
        shutil.copy2(str(source_path), str(original_dest))

        # Proof: resize + strip EXIF + watermark
        from PIL import Image
        from preprocessor.watermark import apply_watermark

        img = Image.open(source_path)
        time_exif = _extract_time_exif_bytes(img)

        # Resize so longest edge ≤ proof_size (preserves aspect ratio)
        if max(img.width, img.height) > config.proof_size:
            img = img.copy()
            img.thumbnail((config.proof_size, config.proof_size), Image.LANCZOS)

        # Apply watermark
        img = apply_watermark(img, config)

        save_kwargs = {
            "format": "JPEG",
            "quality": config.proof_quality,
            "optimize": True,
            "progressive": True,
        }
        if time_exif:
            save_kwargs["exif"] = time_exif

        img.save(str(proof_dest), **save_kwargs)

        bib_candidates: list[str] = []
        if config.auto_bib_scan_enabled:
            detections = scan_bibs_for_photo(str(proof_dest), config)
            bib_candidates = [d.bib for d in detections]

    except Exception as exc:
        return ProcessResult(source=source, success=False, error=str(exc))

    return ProcessResult(source=source, success=True, bib_candidates=bib_candidates)
