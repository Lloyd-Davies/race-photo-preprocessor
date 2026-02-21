"""Persistence helpers for scanned bib results."""
from __future__ import annotations

import csv
from pathlib import Path


def bib_csv_path(output_root: Path, event_slug: str) -> Path:
    return output_root / "bibs" / event_slug / "bib_tags.csv"


def ensure_bib_csv(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["photo_id", "bib", "confidence"])
        writer.writeheader()


def load_bib_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []

    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            photo_id = (row.get("photo_id") or "").strip()
            bib = (row.get("bib") or "").strip()
            confidence = (row.get("confidence") or "1.0").strip()
            if not photo_id or not bib:
                continue
            rows.append({"photo_id": photo_id, "bib": bib, "confidence": confidence})
    return rows


def merge_and_save_bibs(path: Path, photo_id: str, bibs: list[str], confidence: float = 1.0) -> None:
    if not bibs:
        return

    existing = load_bib_rows(path)
    seen = {(r["photo_id"], r["bib"]) for r in existing}

    for bib in bibs:
        key = (photo_id, str(bib))
        if key in seen:
            continue
        existing.append(
            {
                "photo_id": photo_id,
                "bib": str(bib),
                "confidence": f"{confidence:.3f}",
            }
        )
        seen.add(key)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["photo_id", "bib", "confidence"])
        writer.writeheader()
        writer.writerows(existing)
