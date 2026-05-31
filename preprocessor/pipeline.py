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
    proof_jpeg_mode: str = "fast"        # "fast" or "compat"
    auto_bib_scan_enabled: bool = False
    auto_bib_scan_backend: str = "none"
    ocr_device: str = "auto"             # "auto", "cpu", or "cuda"
    auto_bib_min_confidence: int = 70
    auto_bib_enforce_min_digits: bool = False
    auto_bib_min_digits: int = 3


@dataclass
class ProcessResult:
    source: str
    success: bool
    photo_id: str = ""           # assigned output name stem (e.g. bmc-2025-0001)
    skipped: bool = False
    error: str | None = None
    bib_candidates: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)


_EXIF_IFD_TAG = 0x8769
_EXIF_DATETIME_TAG = 0x0132  # DateTime
_EXIF_CAPTURE_TIME_TAG = 0x9003  # DateTimeOriginal
_EXIF_DIGITIZED_TIME_TAG = 0x9004  # DateTimeDigitized
_EXIF_TIME_SUBIFD_TAGS = (
    _EXIF_CAPTURE_TIME_TAG,
    _EXIF_DIGITIZED_TIME_TAG,
    0x9010,  # OffsetTime
    0x9011,  # OffsetTimeOriginal
    0x9012,  # OffsetTimeDigitized
    0x9290,  # SubSecTime
    0x9291,  # SubSecTimeOriginal
    0x9292,  # SubSecTimeDigitized
)


def _extract_time_exif_bytes(source_img) -> bytes | None:
    exif = source_img.getexif()
    if not exif:
        return None

    from PIL import Image

    try:
        source_sub_ifd = exif.get_ifd(_EXIF_IFD_TAG) or {}
    except Exception:
        source_sub_ifd = {}

    def read_time_tag(tag: int):
        if tag in source_sub_ifd:
            return source_sub_ifd[tag]
        if tag in exif:
            return exif[tag]
        return None

    capture_time = (
        read_time_tag(_EXIF_CAPTURE_TIME_TAG)
        or read_time_tag(_EXIF_DIGITIZED_TIME_TAG)
        or exif.get(_EXIF_DATETIME_TAG)
    )
    if not capture_time:
        return None

    keep = Image.Exif()
    keep[_EXIF_DATETIME_TAG] = capture_time

    keep_sub_ifd = {}
    for tag in _EXIF_TIME_SUBIFD_TAGS:
        value = read_time_tag(tag)
        if value is not None:
            keep_sub_ifd[tag] = value

    if _EXIF_CAPTURE_TIME_TAG not in keep_sub_ifd:
        keep_sub_ifd[_EXIF_CAPTURE_TIME_TAG] = capture_time
    if _EXIF_DIGITIZED_TIME_TAG not in keep_sub_ifd:
        keep_sub_ifd[_EXIF_DIGITIZED_TIME_TAG] = capture_time

    keep[_EXIF_IFD_TAG] = keep_sub_ifd

    return keep.tobytes() if len(keep) > 0 else None


def process_photo(source: str, config: ProcessConfig, photo_id: str | None = None) -> ProcessResult:
    """
    Process a single photo: copy as original, generate resized/watermarked proof.

    photo_id overrides the output filename stem.  If omitted the source
    filename stem is used (legacy behaviour).  The assigned photo_id is
    always recorded in the returned ProcessResult.

    Original: pixel-perfect copy, EXIF preserved.
    Proof: resized to longest edge ≤ proof_size, watermark applied, capture-time EXIF preserved.
    """
    import shutil
    import time

    timings: dict[str, float] = {}
    total_started = time.perf_counter()

    def mark(stage: str, started: float) -> None:
        timings[stage] = time.perf_counter() - started

    source_path = Path(source)
    if not source_path.exists():
        return ProcessResult(
            source=source,
            success=False,
            photo_id=photo_id or source_path.stem,
            error="File not found",
            timings=timings,
        )

    assigned_id = photo_id if photo_id else source_path.stem
    proofs_dir = config.output_root / "proofs" / config.event_slug
    originals_dir = config.output_root / "originals" / config.event_slug
    proofs_dir.mkdir(parents=True, exist_ok=True)
    originals_dir.mkdir(parents=True, exist_ok=True)

    original_dest = originals_dir / f"{assigned_id}.jpg"
    proof_dest = proofs_dir / f"{assigned_id}.jpg"

    if config.skip_existing and original_dest.exists() and proof_dest.exists():
        bib_candidates: list[str] = []
        if config.auto_bib_scan_enabled:
            stage_started = time.perf_counter()
            detections = scan_bibs_for_photo(str(proof_dest), config)
            mark("ocr", stage_started)
            bib_candidates = [d.bib for d in detections]
        mark("total", total_started)
        return ProcessResult(
            source=source,
            success=True,
            photo_id=assigned_id,
            skipped=True,
            bib_candidates=bib_candidates,
            timings=timings,
        )

    try:
        # Original: preserved as pixel-perfect copy
        stage_started = time.perf_counter()
        shutil.copy2(str(source_path), str(original_dest))
        mark("copy_original", stage_started)

        # Proof: resize + strip EXIF + watermark
        from PIL import Image
        from preprocessor.watermark import apply_watermark

        stage_started = time.perf_counter()
        img = Image.open(source_path)
        time_exif = _extract_time_exif_bytes(img)
        original_longest_edge = max(img.width, img.height)
        needs_resize = original_longest_edge > config.proof_size
        if original_longest_edge > config.proof_size * 2:
            try:
                img.draft("RGB", (config.proof_size * 2, config.proof_size * 2))
            except Exception:
                pass
        mark("open_decode_hint", stage_started)

        # Resize so longest edge ≤ proof_size (preserves aspect ratio)
        if needs_resize:
            stage_started = time.perf_counter()
            img = img.copy()
            img.thumbnail((config.proof_size, config.proof_size), Image.LANCZOS)
            mark("resize", stage_started)

        # Apply watermark
        stage_started = time.perf_counter()
        img = apply_watermark(img, config)
        mark("watermark", stage_started)

        save_kwargs = {
            "format": "JPEG",
            "quality": config.proof_quality,
        }
        if config.proof_jpeg_mode == "compat":
            save_kwargs.update(
                {
                    "optimize": True,
                    "progressive": True,
                }
            )
        if time_exif:
            save_kwargs["exif"] = time_exif

        stage_started = time.perf_counter()
        img.save(str(proof_dest), **save_kwargs)
        mark("save_proof", stage_started)

        bib_candidates: list[str] = []
        if config.auto_bib_scan_enabled:
            stage_started = time.perf_counter()
            detections = scan_bibs_for_photo(str(proof_dest), config)
            mark("ocr", stage_started)
            bib_candidates = [d.bib for d in detections]

    except Exception as exc:
        mark("total", total_started)
        return ProcessResult(
            source=source,
            success=False,
            photo_id=assigned_id,
            error=str(exc),
            timings=timings,
        )

    mark("total", total_started)
    return ProcessResult(
        source=source,
        success=True,
        photo_id=assigned_id,
        bib_candidates=bib_candidates,
        timings=timings,
    )
