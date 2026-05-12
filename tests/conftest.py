"""Test fixtures and shared utilities."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def reset_store_api_thread_state():
    from preprocessor.store_api import (
        _clear_thread_auth_cache_for_tests,
        _close_thread_client_for_tests,
    )

    _clear_thread_auth_cache_for_tests()
    _close_thread_client_for_tests()
    yield
    _clear_thread_auth_cache_for_tests()
    _close_thread_client_for_tests()


@pytest.fixture
def sample_jpeg(tmp_path: Path) -> Path:
    """Create a minimal valid JPEG file (1×1 white pixel)."""
    from PIL import Image
    p = tmp_path / "sample.jpg"
    Image.new("RGB", (1, 1), color=(255, 255, 255)).save(str(p), format="JPEG")
    return p


@pytest.fixture
def large_jpeg(tmp_path: Path) -> Path:
    """Create a 3000×2000 px synthetic JPEG (larger than default proof_size=1600)."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (3000, 2000), color=(100, 149, 237))
    draw = ImageDraw.Draw(img)
    draw.rectangle([200, 200, 2800, 1800], outline=(255, 255, 255), width=10)
    p = tmp_path / "large.jpg"
    img.save(str(p), format="JPEG", quality=95)
    return p


@pytest.fixture
def photo_folder(tmp_path: Path, sample_jpeg: Path) -> Path:
    """A folder containing 3 JPEG files and one non-JPEG."""
    folder = tmp_path / "photos"
    folder.mkdir()
    for name in ["DSC_001.jpg", "DSC_002.jpg", "DSC_003.jpg"]:
        (folder / name).write_bytes(sample_jpeg.read_bytes())
    (folder / "notes.txt").write_text("not a photo")
    return folder
