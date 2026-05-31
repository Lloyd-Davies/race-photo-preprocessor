from __future__ import annotations

from pathlib import Path

from PIL import Image

from preprocessor.pipeline import ProcessConfig
from preprocessor.watermark import apply_watermark, clear_watermark_cache, watermark_cache_info


def test_watermark_overlay_is_reused_for_same_size_and_settings(tmp_path: Path) -> None:
    config = ProcessConfig(event_slug="ev", output_root=tmp_path, watermark_text="Test")
    clear_watermark_cache()

    apply_watermark(Image.new("RGB", (1600, 1067), (100, 100, 100)), config)
    first = watermark_cache_info()
    apply_watermark(Image.new("RGB", (1600, 1067), (120, 120, 120)), config)
    second = watermark_cache_info()

    assert first["overlays"] == 1
    assert second["overlays"] == 1
    assert second["fonts"] == first["fonts"]


def test_watermark_overlay_cache_splits_on_size(tmp_path: Path) -> None:
    config = ProcessConfig(event_slug="ev", output_root=tmp_path, watermark_text="Test")
    clear_watermark_cache()

    apply_watermark(Image.new("RGB", (1600, 1067), (100, 100, 100)), config)
    apply_watermark(Image.new("RGB", (1200, 800), (100, 100, 100)), config)

    assert watermark_cache_info()["overlays"] == 2
