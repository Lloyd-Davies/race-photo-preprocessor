"""Tests for the rename/photo-ID assignment module."""
from __future__ import annotations

from pathlib import Path

import pytest

from preprocessor.rename import (
    build_rename_plan,
    make_photo_id,
    natural_sort_key,
    write_rename_map,
)


# ── make_photo_id ──────────────────────────────────────────────────────────────

def test_make_photo_id_format() -> None:
    assert make_photo_id("bmc-2025", 1) == "bmc-2025-0001"
    assert make_photo_id("bmc-2025", 99) == "bmc-2025-0099"
    assert make_photo_id("bmc-2025", 1000) == "bmc-2025-1000"


def test_make_photo_id_slug_preserved() -> None:
    assert make_photo_id("my-event-name", 5) == "my-event-name-0005"


# ── natural_sort_key ───────────────────────────────────────────────────────────

def test_natural_sort_numeric_order(tmp_path: Path) -> None:
    """Numeric parts must sort numerically, not lexicographically."""
    names = ["DSC_0100.jpg", "DSC_0020.jpg", "DSC_0009.jpg", "DSC_0099.jpg"]
    paths = [tmp_path / n for n in names]
    sorted_paths = sorted(paths, key=natural_sort_key)
    assert [p.name for p in sorted_paths] == [
        "DSC_0009.jpg",
        "DSC_0020.jpg",
        "DSC_0099.jpg",
        "DSC_0100.jpg",
    ]


def test_natural_sort_mixed_prefix(tmp_path: Path) -> None:
    """Files with different prefixes should sort by prefix first, then number."""
    names = ["B_002.jpg", "A_010.jpg", "A_002.jpg", "B_001.jpg"]
    paths = [tmp_path / n for n in names]
    sorted_paths = sorted(paths, key=natural_sort_key)
    assert [p.name for p in sorted_paths] == [
        "A_002.jpg",
        "A_010.jpg",
        "B_001.jpg",
        "B_002.jpg",
    ]


# ── build_rename_plan ──────────────────────────────────────────────────────────

def test_build_rename_plan_order(tmp_path: Path) -> None:
    """Counter must reflect natural sort order of original names."""
    names = ["DSC_0003.jpg", "DSC_0001.jpg", "DSC_0002.jpg"]
    paths = [tmp_path / n for n in names]

    plan = build_rename_plan(paths, "race-2025")

    sources = [p.name for p, _ in plan]
    ids = [pid for _, pid in plan]
    assert sources == ["DSC_0001.jpg", "DSC_0002.jpg", "DSC_0003.jpg"]
    assert ids == ["race-2025-0001", "race-2025-0002", "race-2025-0003"]


def test_build_rename_plan_single(tmp_path: Path) -> None:
    plan = build_rename_plan([tmp_path / "IMG_001.jpg"], "ev")
    assert plan == [(tmp_path / "IMG_001.jpg", "ev-0001")]


def test_build_rename_plan_empty() -> None:
    assert build_rename_plan([], "ev") == []


# ── write_rename_map ───────────────────────────────────────────────────────────

def test_write_rename_map_creates_csv(tmp_path: Path) -> None:
    plan = [
        (Path("/src/DSC_0001.jpg"), "ev-0001"),
        (Path("/src/DSC_0002.jpg"), "ev-0002"),
    ]
    dest = tmp_path / "originals" / "ev" / "_rename_map.csv"

    write_rename_map(plan, dest)

    assert dest.exists()
    lines = dest.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "original_name,photo_id"
    assert lines[1] == "DSC_0001.jpg,ev-0001"
    assert lines[2] == "DSC_0002.jpg,ev-0002"


def test_write_rename_map_creates_parent_dirs(tmp_path: Path) -> None:
    dest = tmp_path / "deep" / "nested" / "map.csv"
    write_rename_map([], dest)
    assert dest.exists()
