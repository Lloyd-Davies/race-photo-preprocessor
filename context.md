# race-photo-preprocessor

## Purpose

A local CLI tool run by the photographer on their own machine after editing.
Takes a folder of exported JPGs (from Lightroom, Capture One, etc.) for a specific
race event and produces the two directory trees consumed by **race-photo-store**:

```
output/
  proofs/
    {event-slug}/
      {photo_id}.jpg    ← watermarked, web-sized, EXIF-stripped
  originals/
    {event-slug}/
      {photo_id}.jpg    ← full-resolution file, ready to be zipped for purchase
```

`photo_id` = the stem of the source filename (e.g. `DSC_4821.jpg` → `DSC_4821`).

The output directory is then either:
- **Local dev**: pointed at `race-photo-store/.localdata/photos/`
- **VM**: rsync'd / scp'd to `/mnt/pstore/photos/` on the Oracle Cloud server

After files are in place, the photographer logs into the admin UI and runs
**"Ingest"** — the API scans `proofs/{slug}/*.jpg`, registers each file in the
database, and the gallery becomes live.

---

## Integration contract with race-photo-store

From `race-photo-store/api/app/routes/admin.py`:

```python
storage_root = Path(settings.STORAGE_ROOT)   # /data/photos (or .localdata/photos locally)
proofs_dir   = storage_root / "proofs" / event.slug
# Ingest scans: proofs_dir.glob("*.jpg")
# photo_id     = filepath.stem
# proof_path   = f"proofs/{event.slug}/{photo_id}.jpg"
# original_path= f"originals/{event.slug}/{photo_id}.jpg"
# state = READY if (storage_root / original_path).exists() else MISSING
```

From `race-photo-store/worker/tasks/build_zip.py`:

```python
original = storage_root / photo.original_path   # originals/{slug}/{photo_id}.jpg
zf.write(original, arcname=f"{photo_id}.jpg")
```

From `race-photo-store/nginx/nginx.conf`:

```nginx
location /proofs/ {
    alias /srv/photos/proofs/;   # proof images served directly by nginx
}
```

Key constraints:
- Files **must** be `.jpg` (lowercase extension)
- The `photo_id` (filename stem) **must be identical** in both `proofs/` and `originals/`
- Proofs are served publicly via nginx — they must carry a visible watermark
- Originals are only accessed server-side (zipped) — no watermark needed

---

## CLI design

```
preprocess [OPTIONS] INPUT_DIR

Options:
  --event        TEXT    Event slug (e.g. bmc-indoors-2025)  [required]
  --output       PATH    Root output directory
                         Default: ./output
  --watermark    TEXT    Watermark text overlaid on proofs
                         Default: "© Race Photos"
  --proof-size   INT     Longest edge of proof in pixels     [default: 1600]
  --proof-quality INT    JPEG quality for proofs (1-95)      [default: 82]
  --workers      INT     Parallel worker processes           [default: CPU count]
  --skip-existing        Skip files already present in output [default: true]
  --dry-run              Print what would be done, write nothing
  --verbose / -v         Show per-file progress
```

### Example usage

```bash
# Local dev — write straight into race-photo-store's data folder
preprocess ~/exports/bmc-indoors-2025/ \
  --event bmc-indoors-2025 \
  --output c:/GitHub/race-photo-store/.localdata/photos \
  --watermark "© BMC 2025"

# Production — write to a staging folder, then rsync to VM
preprocess ~/exports/bmc-indoors-2025/ \
  --event bmc-indoors-2025 \
  --output ~/photostore-staging \
  --watermark "© BMC 2025"

rsync -avz ~/photostore-staging/ user@vm:/mnt/pstore/photos/
```

---

## Processing pipeline (per photo)

```
source.jpg
   │
   ├─► originals/{slug}/{stem}.jpg
   │     • Copy as-is (no reprocessing)
   │     • EXIF preserved
   │
   └─► proofs/{slug}/{stem}.jpg
         1. Open with Pillow
         2. Auto-orient using EXIF rotation tag
         3. Resize: longest edge → proof-size (default 1600px), Lanczos
         4. Strip all EXIF metadata (privacy: remove GPS, camera serial, etc.)
         5. Composite watermark:
              • Semi-transparent text (white + drop shadow) in the bottom-right
              • Font size proportional to image width (~3%)
              • Optionally tile a logo PNG across image at low opacity
         6. Save as JPEG, quality=proof-quality, progressive=True
```

---

## Watermark specification

Proofs need to be clearly marked but not obscure the photo.

**Default behaviour:**
- Text: configurable string (e.g. `"© BMC Indoors 2025 | racephotos.example.com"`)
- Position: bottom-right, 1% margin
- Font: bundled TrueType (e.g. DejaVu Sans or similar open-font)
- Font size: max(24px, image_width * 0.028)
- Colour: white text with semi-transparent grey drop-shadow
- Opacity: text at 85% alpha

**Optional logo mode** (`--watermark-logo path/to/logo.png`):
- Tile the logo across the proof at ~8% opacity (deters crop-based bypass)
- Plus the text watermark in the corner

---

## Project structure

```
race-photo-preprocessor/
  preprocess/
    __init__.py
    cli.py          # Click entrypoint
    pipeline.py     # Per-photo processing logic
    watermark.py    # Watermark compositing
    fonts/          # Bundled .ttf files
  tests/
    test_pipeline.py
    test_watermark.py
    fixtures/       # Small test JPEGs
  pyproject.toml
  README.md
```

---

## Stack

| Concern         | Library             |
|-----------------|---------------------|
| CLI             | Click 8             |
| Image processing| Pillow 10           |
| Progress UI     | Rich (progress bar) |
| Parallelism     | `concurrent.futures.ProcessPoolExecutor` |
| Tests           | pytest + pytest-tmp-path |

Python ≥ 3.11. No external services required — runs fully offline.

---

## Output summary / report

After processing, print a Rich table:

```
Event:    bmc-indoors-2025
Input:    ~/exports/bmc-indoors-2025/   (312 files)
Output:   .localdata/photos/

┌──────────────┬───────┐
│ Category     │ Count │
├──────────────┼───────┤
│ Processed    │  308  │
│ Skipped      │    4  │
│ Errors       │    0  │
│ Total time   │ 1m 42s│
└──────────────┴───────┘

Next step: run "Ingest" in the admin UI for event bmc-indoors-2025
```

---

## Development phases

1. **Phase 1** — Scaffold: `pyproject.toml`, CLI entrypoint, basic copy-only mode (no watermark), test fixtures
2. **Phase 2** — Proof generation: resize + EXIF strip + basic text watermark
3. **Phase 3** — Watermark quality: font bundling, proportional sizing, drop shadow, opacity
4. **Phase 4** — Parallelism + progress bar (Rich)
5. **Phase 5** — Logo watermark tiling mode
6. **Phase 6** — Tests: pipeline correctness, watermark presence, output structure, skip-existing logic
