"""Benchmark proof generation and optional OCR on a folder of JPEG photos."""
from __future__ import annotations

import argparse
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from preprocessor.bib_ocr import describe_ocr_runtime
from preprocessor.bib_scan import scan_bibs_for_photo
from preprocessor.pipeline import ProcessConfig, process_photo


def _jpgs(folder: Path, limit: int) -> list[Path]:
    paths = sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg"}
    )
    return paths[:limit] if limit > 0 else paths


def _worker_count(requested: int, total: int) -> int:
    if requested > 0:
        return min(requested, total)
    import os

    cpu = os.cpu_count() or 4
    return max(1, min(total, max(2, cpu - 1)))


def benchmark_proofs(paths: list[Path], config: ProcessConfig, workers: int) -> None:
    started = time.perf_counter()
    timings: dict[str, float] = {}
    ok = 0

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="proof-bench") as ex:
        futures = {
            ex.submit(process_photo, str(path), config, f"{config.event_slug}-{idx:04d}"): path
            for idx, path in enumerate(paths, start=1)
        }
        for future in as_completed(futures):
            result = future.result()
            if result.success:
                ok += 1
            for key, value in result.timings.items():
                timings[key] = timings.get(key, 0.0) + value

    elapsed = time.perf_counter() - started
    rate = (ok / elapsed * 60.0) if elapsed else 0.0
    print(f"Proofs: {ok}/{len(paths)} ok in {elapsed:.2f}s ({rate:.1f} photos/min, workers={workers})")
    for key in sorted(timings):
        print(f"  {key}: {timings[key]:.2f}s total")


def benchmark_ocr(paths: list[Path], config: ProcessConfig, workers: int) -> None:
    started = time.perf_counter()
    ok = 0
    detections = 0

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ocr-bench") as ex:
        futures = {ex.submit(scan_bibs_for_photo, str(path), config): path for path in paths}
        for future in as_completed(futures):
            found = future.result()
            ok += 1
            detections += len(found)

    elapsed = time.perf_counter() - started
    rate = (ok / elapsed * 60.0) if elapsed else 0.0
    print(f"OCR: {ok}/{len(paths)} scanned in {elapsed:.2f}s ({rate:.1f} images/min, workers={workers})")
    print(f"  detections: {detections}")
    print(f"  {describe_ocr_runtime(config.ocr_device)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Folder containing JPEG photos")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of photos to benchmark")
    parser.add_argument("--workers", type=int, default=0, help="Proof worker count; 0 uses auto")
    parser.add_argument("--ocr-workers", type=int, default=0, help="OCR worker count; 0 uses auto")
    parser.add_argument("--ocr", action="store_true", help="Also benchmark OCR on the source photos")
    parser.add_argument("--ocr-device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--jpeg-mode", choices=["fast", "compat"], default="fast")
    parser.add_argument("--event-slug", default="bench")
    parser.add_argument("--output-root", type=Path, default=None)
    args = parser.parse_args()

    paths = _jpgs(args.folder, args.limit)
    if not paths:
        print("No JPEG photos found.")
        return 1

    temp_root = None
    output_root = args.output_root
    if output_root is None:
        temp_root = Path(tempfile.mkdtemp(prefix="rpp_bench_"))
        output_root = temp_root

    try:
        proof_config = ProcessConfig(
            event_slug=args.event_slug,
            output_root=output_root,
            skip_existing=False,
            proof_jpeg_mode=args.jpeg_mode,
        )
        proof_workers = _worker_count(args.workers, len(paths))
        benchmark_proofs(paths, proof_config, proof_workers)

        if args.ocr:
            ocr_config = ProcessConfig(
                event_slug=args.event_slug,
                output_root=output_root,
                auto_bib_scan_enabled=True,
                auto_bib_scan_backend="ocr",
                ocr_device=args.ocr_device,
            )
            ocr_workers = _worker_count(args.ocr_workers, len(paths))
            benchmark_ocr(paths, ocr_config, ocr_workers)
    finally:
        if temp_root is not None:
            shutil.rmtree(temp_root, ignore_errors=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
