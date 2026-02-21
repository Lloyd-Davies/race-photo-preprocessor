"""Tests for the image processing pipeline."""
from __future__ import annotations

from pathlib import Path

import pytest

from preprocessor.pipeline import ProcessConfig, ProcessResult, process_photo


# ── Smoke / basic behaviour ───────────────────────────────────────────────────

def test_process_creates_both_outputs(photo_folder: Path, tmp_path: Path) -> None:
    output = tmp_path / "output"
    config = ProcessConfig(event_slug="test-event", output_root=output)
    source = str(photo_folder / "DSC_001.jpg")

    result = process_photo(source, config)

    assert result.success
    assert not result.skipped
    assert (output / "proofs" / "test-event" / "DSC_001.jpg").exists()
    assert (output / "originals" / "test-event" / "DSC_001.jpg").exists()


def test_process_skip_existing(photo_folder: Path, tmp_path: Path) -> None:
    output = tmp_path / "output"
    config = ProcessConfig(event_slug="test-event", output_root=output, skip_existing=True)
    source = str(photo_folder / "DSC_001.jpg")

    r1 = process_photo(source, config)
    assert r1.success and not r1.skipped

    r2 = process_photo(source, config)
    assert r2.success and r2.skipped


def test_process_no_skip(photo_folder: Path, tmp_path: Path) -> None:
    output = tmp_path / "output"
    config = ProcessConfig(event_slug="test-event", output_root=output, skip_existing=False)
    source = str(photo_folder / "DSC_001.jpg")

    process_photo(source, config)
    r2 = process_photo(source, config)
    assert r2.success and not r2.skipped


def test_process_missing_file(tmp_path: Path) -> None:
    config = ProcessConfig(event_slug="test-event", output_root=tmp_path)
    result = process_photo("/nonexistent/file.jpg", config)
    assert not result.success
    assert result.error is not None


def test_photo_id_is_stem(photo_folder: Path, tmp_path: Path) -> None:
    output = tmp_path / "output"
    config = ProcessConfig(event_slug="my-event", output_root=output)
    source = str(photo_folder / "DSC_002.jpg")

    process_photo(source, config)

    assert (output / "proofs" / "my-event" / "DSC_002.jpg").exists()
    assert (output / "originals" / "my-event" / "DSC_002.jpg").exists()
    assert not (output / "proofs" / "my-event" / "DSC_001.jpg").exists()


# ── Phase 3 — Pillow pipeline ─────────────────────────────────────────────────

def test_proof_is_resized(large_jpeg: Path, tmp_path: Path) -> None:
    """A 3000×2000 source must produce a proof with longest edge == 1600."""
    from PIL import Image

    output = tmp_path / "output"
    config = ProcessConfig(event_slug="ev", output_root=output, proof_size=1600)
    result = process_photo(str(large_jpeg), config)

    assert result.success
    proof = output / "proofs" / "ev" / "large.jpg"
    img = Image.open(proof)
    assert max(img.width, img.height) == 1600
    assert img.width == 1600
    assert abs(img.height - 1067) <= 2  # 2000 * 1600/3000 ≈ 1067


def test_original_not_resized(large_jpeg: Path, tmp_path: Path) -> None:
    """Original must be copied as-is, not resized."""
    from PIL import Image

    output = tmp_path / "output"
    config = ProcessConfig(event_slug="ev", output_root=output, proof_size=1600)
    process_photo(str(large_jpeg), config)

    original = output / "originals" / "ev" / "large.jpg"
    img = Image.open(original)
    assert img.width == 3000
    assert img.height == 2000


def test_small_image_not_upscaled(photo_folder: Path, tmp_path: Path) -> None:
    """Images smaller than proof_size must not be upscaled."""
    from PIL import Image

    output = tmp_path / "output"
    config = ProcessConfig(event_slug="ev", output_root=output, proof_size=1600)
    source = str(photo_folder / "DSC_001.jpg")
    process_photo(source, config)

    proof = output / "proofs" / "ev" / "DSC_001.jpg"
    img = Image.open(proof)
    assert img.width == 1
    assert img.height == 1


def test_watermark_changes_pixels(large_jpeg: Path, tmp_path: Path) -> None:
    """Proof with watermark must differ from proof without watermark."""
    from PIL import Image
    import numpy as np

    out_wm  = tmp_path / "wm"
    out_now = tmp_path / "nowm"

    config_wm = ProcessConfig(
        event_slug="ev", output_root=out_wm,
        watermark_text="© Test", watermark_opacity=100,
    )
    config_no = ProcessConfig(
        event_slug="ev", output_root=out_now,
        watermark_text="",
    )
    process_photo(str(large_jpeg), config_wm)
    process_photo(str(large_jpeg), config_no)

    arr_wm = np.array(Image.open(out_wm  / "proofs" / "ev" / "large.jpg"))
    arr_no = np.array(Image.open(out_now / "proofs" / "ev" / "large.jpg"))
    assert not (arr_wm == arr_no).all(), "Watermarked proof must differ from unwatermarked"


def test_watermark_pattern_affects_multiple_regions(large_jpeg: Path, tmp_path: Path) -> None:
    """Diagonal repeating watermark should affect multiple image regions."""
    from PIL import Image
    import numpy as np

    out_wm  = tmp_path / "wm"
    out_now = tmp_path / "nowm"

    config_wm = ProcessConfig(
        event_slug="ev", output_root=out_wm,
        watermark_text="© Test", watermark_opacity=100,
        watermark_position="bottom-right",
    )
    config_no = ProcessConfig(
        event_slug="ev", output_root=out_now,
        watermark_text="",
    )
    process_photo(str(large_jpeg), config_wm)
    process_photo(str(large_jpeg), config_no)

    wm = np.array(Image.open(out_wm  / "proofs" / "ev" / "large.jpg"), dtype=float)
    no = np.array(Image.open(out_now / "proofs" / "ev" / "large.jpg"), dtype=float)

    h, w = wm.shape[:2]
    tl = (wm[: int(h * 0.25), : int(w * 0.25)] - no[: int(h * 0.25), : int(w * 0.25)]).mean()
    center = (
        wm[int(h * 0.4): int(h * 0.6), int(w * 0.4): int(w * 0.6)]
        - no[int(h * 0.4): int(h * 0.6), int(w * 0.4): int(w * 0.6)]
    ).mean()
    br = (wm[int(h * 0.75):, int(w * 0.75):] - no[int(h * 0.75):, int(w * 0.75):]).mean()

    assert tl > 0, "Top-left should show watermark pattern"
    assert center > 0, "Center should show watermark pattern"
    assert br > 0, "Bottom-right should show watermark pattern"


def test_proof_preserves_capture_datetime_exif(tmp_path: Path) -> None:
    """Proof output must retain capture datetime EXIF tags for downstream time filters."""
    from PIL import Image

    source = tmp_path / "source.jpg"
    output = tmp_path / "output"

    exif = Image.Exif()
    exif[0x9003] = "2026:02:21 09:12:34"  # DateTimeOriginal
    exif[0x9004] = "2026:02:21 09:12:34"  # DateTimeDigitized
    exif[0x0132] = "2026:02:21 09:12:34"  # DateTime

    img = Image.new("RGB", (2200, 1460), (140, 130, 120))
    img.save(source, format="JPEG", exif=exif.tobytes())

    config = ProcessConfig(event_slug="ev", output_root=output, proof_size=1600)
    result = process_photo(str(source), config)
    assert result.success

    proof = output / "proofs" / "ev" / "source.jpg"
    proof_exif = Image.open(proof).getexif()

    assert proof_exif.get(0x9003) == "2026:02:21 09:12:34"
    assert proof_exif.get(0x9004) == "2026:02:21 09:12:34"
    assert proof_exif.get(0x0132) == "2026:02:21 09:12:34"


def test_auto_bib_scan_scaffold_is_noop(photo_folder: Path, tmp_path: Path) -> None:
    """Enabling auto bib scan scaffold should not fail and returns no detections yet."""
    output = tmp_path / "output"
    config = ProcessConfig(
        event_slug="test-event",
        output_root=output,
        auto_bib_scan_enabled=True,
        auto_bib_scan_backend="ocr",
        auto_bib_min_confidence=75,
    )

    result = process_photo(str(photo_folder / "DSC_001.jpg"), config)
    assert result.success
    assert result.bib_candidates == []
