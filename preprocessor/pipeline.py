"""Image processing pipeline — pure functions, no Qt. (Phase 3)"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProcessConfig:
    event_slug: str
    output_root: Path
    watermark_text: str = "© Race Photos"
    watermark_opacity: int = 85          # 0-100
    watermark_position: str = "bottom-right"
    proof_size: int = 1600               # longest edge px
    proof_quality: int = 82              # JPEG quality
    skip_existing: bool = True
    watermark_logo_path: str | None = None
    watermark_logo_opacity: int = 15     # 0-100


@dataclass
class ProcessResult:
    source: str
    success: bool
    skipped: bool = False
    error: str | None = None


def process_photo(source: str, config: ProcessConfig) -> ProcessResult:
    """
    Process a single photo: copy as original, generate watermarked proof.

    Phase 1: copy-only (no watermark).
    Phase 3+: full pipeline with resize + watermark.
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
        return ProcessResult(source=source, success=True, skipped=True)

    try:
        # Original: straight copy
        shutil.copy2(str(source_path), str(original_dest))

        # Proof: copy for now; Phase 3 will add resize + watermark
        shutil.copy2(str(source_path), str(proof_dest))

    except Exception as exc:
        return ProcessResult(source=source, success=False, error=str(exc))

    return ProcessResult(source=source, success=True)
