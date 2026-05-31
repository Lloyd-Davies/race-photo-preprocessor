# race-photo-preprocessor

Desktop app for preparing race photos before upload to race-photo-store.

It imports camera files, generates watermarked proof JPEGs, keeps full-resolution originals, and helps with downstream deployment/indexing workflows.

## Features

- Import and batch-process photos into:
  - `proofs/<event-slug>/` (resized + watermarked)
  - `originals/<event-slug>/` (full-resolution copies)
- Live progress table and last-generated proof preview
- Configurable watermark controls in Process tab:
  - text
  - opacity
  - pattern (`Diagonal repeat` / `Single corner`)
  - angle
  - spacing X / spacing Y
  - font scale
  - position (single-corner mode)
- Performance controls:
  - dedicated proof worker count
  - fast or compatibility proof JPEG output
  - dedicated OCR worker count
  - OCR device mode (`Auto`, `CPU`, `CUDA`)
- Light/dark theme toggle (persisted via QSettings)
- Persisted project settings (event, output paths, API details)

## Tech stack

- Python 3.11+
- PySide6 (GUI)
- Pillow (image pipeline)
- Paramiko + HTTPX (deployment/API helpers)

## Repository layout

```text
preprocessor/
  app.py               # application entrypoint
  main_window.py       # main window + tab shell
  sidebar.py           # event/output/store controls
  pipeline.py          # processing config + process_photo()
  watermark.py         # watermark renderer
  icons.py             # app icon helper
  tabs/
    import_tab.py
    process_tab.py
    bibs_tab.py
    deploy_tab.py
  workers/
tests/
pyproject.toml
```

## Local development

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

Run the app:

```bash
preprocessor
```

Run tests:

```bash
python -m pytest -q
```

Benchmark a representative folder:

```bash
python scripts/benchmark_processing.py D:\photos\incoming --limit 100 --jpeg-mode fast
python scripts/benchmark_processing.py D:\photos\incoming --ocr --ocr-device auto
```

## Performance notes

Proof generation uses CPU workers. `Fast JPEG` skips the previous optimized/progressive
JPEG save path, which is usually much faster while keeping the same proof dimensions,
quality setting, watermark, and capture-time EXIF tags. `Compat JPEG` keeps the previous
optimized/progressive behavior.

OCR uses RapidOCR through ONNX Runtime. CPU OCR uses one OCR engine per worker thread.
CUDA OCR is optional and only used when `CUDAExecutionProvider` is available; otherwise
the app falls back to CPU. To enable CUDA OCR, install an ONNX Runtime GPU build that
matches the machine's NVIDIA CUDA/cuDNN runtime, then confirm that
`CUDAExecutionProvider` appears in:

```bash
python -c "import onnxruntime as ort; print(ort.get_available_providers())"
```

## Output model

For `event_slug = bmc-indoors` and `output_root = D:/photos`:

- `D:/photos/proofs/bmc-indoors/<photo_id>.jpg`
- `D:/photos/originals/bmc-indoors/<photo_id>.jpg`

## Windows executable builds

GitHub Actions workflows are included:

- `.github/workflows/build-exe.yml`
  - builds Windows executable artifacts for CI runs
- `.github/workflows/release.yml`
  - on tag pushes (`v*`), builds and publishes Release assets:
    - `race-photo-preprocessor-windows.exe`
    - `race-photo-preprocessor-windows.zip`

## Versioning

- Current release tag: `v0.1.0`
- Release title format: `Race Photo Pre-Processor vX.Y.Z`
