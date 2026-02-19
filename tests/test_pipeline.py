"""Tests for the image processing pipeline."""
from __future__ import annotations

from pathlib import Path

import pytest

from preprocessor.pipeline import ProcessConfig, ProcessResult, process_photo


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

    # First run: process
    r1 = process_photo(source, config)
    assert r1.success and not r1.skipped

    # Second run: skip
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
    # No unexpected files
    assert not (output / "proofs" / "my-event" / "DSC_001.jpg").exists()
