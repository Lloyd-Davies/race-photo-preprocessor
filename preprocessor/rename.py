"""Filename assignment for processed photos.

Photos are renamed from their original camera names (e.g. DSC_0001.jpg) to a
consistent slug-based scheme:  {slug}-{counter:04d}.jpg

The counter is assigned in natural-sort order of the original filenames, so
cameras that already produce padded sequential names (DSC_0001 … DSC_9999) get
a predictable mapping.

A mapping CSV is always written next to the originals so the original name can
be recovered if needed.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path


# ── Sorting ───────────────────────────────────────────────────────────────────

def _natural_key(text: str) -> list[int | str]:
    """Split a string into alternating text / integer chunks for natural sort.

    "DSC_0099" → ["DSC_", 99, ""] so numeric parts sort numerically.
    """
    parts: list[int | str] = []
    for chunk in re.split(r"(\d+)", text):
        parts.append(int(chunk) if chunk.isdigit() else chunk.lower())
    return parts


def natural_sort_key(path: Path) -> list[int | str]:
    """Sort key for Path objects based on the filename stem."""
    return _natural_key(path.name)


# ── ID generation ─────────────────────────────────────────────────────────────

def make_photo_id(slug: str, n: int) -> str:
    """Return the photo_id for the nth photo in an event (1-based).

    >>> make_photo_id("bmc-2025", 1)
    'bmc-2025-0001'
    >>> make_photo_id("bmc-2025", 100)
    'bmc-2025-0100'
    """
    return f"{slug}-{n:04d}"


# ── Rename plan ───────────────────────────────────────────────────────────────

def build_rename_plan(paths: list[Path], slug: str) -> list[tuple[Path, str]]:
    """Return [(source_path, photo_id), ...] in natural sort order.

    The counter starts at 1 and is zero-padded to 4 digits.
    """
    sorted_paths = sorted(paths, key=natural_sort_key)
    return [(p, make_photo_id(slug, i)) for i, p in enumerate(sorted_paths, start=1)]


# ── Mapping CSV ───────────────────────────────────────────────────────────────

def write_rename_map(plan: list[tuple[Path, str]], dest: Path) -> None:
    """Write a CSV mapping original_name → photo_id to *dest*.

    dest is the full path to the CSV file; parent dirs are created as needed.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["original_name", "photo_id"])
        writer.writeheader()
        for path, photo_id in plan:
            writer.writerow({"original_name": path.name, "photo_id": photo_id})
