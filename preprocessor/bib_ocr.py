"""OCR adapter for bib scanning.

Backend-neutral interface; currently supports ``none`` and RapidOCR via
ONNX Runtime. CPU OCR uses one RapidOCR engine per worker thread. CUDA OCR,
when available, uses one shared engine to avoid duplicating model memory.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_THREAD_STATE = threading.local()
_CUDA_LOCK = threading.Lock()
_CUDA_ENGINE = None
_CUDA_ENGINE_KEY: tuple[object, ...] | None = None
_DLL_LOAD_LOCK = threading.Lock()
_DLL_PRELOAD_DONE = False
_DLL_HANDLES: list[object] = []
_DLL_DIR_HANDLES: list[object] = []


@dataclass
class OCRRuntimeInfo:
    requested_device: str
    selected_device: str
    provider: str
    available_providers: list[str]
    cuda_available: bool
    fallback_reason: str = ""


@dataclass
class OCRTextCandidate:
    text: str
    confidence: float
    bbox: tuple[int, int, int, int] | None = None


def _normalize_device(device: str | None) -> str:
    value = (device or "auto").strip().lower()
    return value if value in {"auto", "cpu", "cuda"} else "auto"


def _preload_onnxruntime_dlls() -> None:
    global _DLL_PRELOAD_DONE

    with _DLL_LOAD_LOCK:
        if _DLL_PRELOAD_DONE:
            return

        try:
            import os
            import site

            site_roots = [Path(p) for p in site.getsitepackages()]
            dll_dirs = []
            for root in site_roots:
                nvidia_root = root / "nvidia"
                for rel in (
                    "cudnn/bin",
                    "cublas/bin",
                    "cuda_runtime/bin",
                    "cuda_nvrtc/bin",
                    "cufft/bin",
                    "curand/bin",
                    "nvjitlink/bin",
                ):
                    dll_dir = nvidia_root / rel
                    if dll_dir.exists():
                        dll_dirs.append(dll_dir)

            for dll_dir in dll_dirs:
                try:
                    _DLL_DIR_HANDLES.append(os.add_dll_directory(str(dll_dir)))
                except Exception:
                    pass

            try:
                import onnxruntime as ort  # type: ignore[import-not-found]

                preload = getattr(ort, "preload_dlls", None)
                if callable(preload):
                    preload(directory="")
            except Exception:
                pass

            # cuDNN can lazily load frontend engine DLLs by filename. Explicitly
            # loading and retaining the handles prevents Windows from missing
            # wheel-provided sublibraries such as cudnn_engines_tensor_ir64_9.dll.
            try:
                import ctypes

                for dll_dir in dll_dirs:
                    if dll_dir.name != "bin" or dll_dir.parent.name != "cudnn":
                        continue
                    for dll_path in sorted(dll_dir.glob("cudnn*.dll")):
                        try:
                            _DLL_HANDLES.append(ctypes.WinDLL(str(dll_path)))
                        except OSError:
                            pass
            except Exception:
                pass
        finally:
            _DLL_PRELOAD_DONE = True


def _available_onnx_providers() -> list[str]:
    try:
        _preload_onnxruntime_dlls()
        import onnxruntime as ort  # type: ignore[import-not-found]

        return list(ort.get_available_providers())
    except Exception:
        return []


def get_ocr_runtime_info(device: str | None = "auto") -> OCRRuntimeInfo:
    requested = _normalize_device(device)
    providers = _available_onnx_providers()
    cuda_available = "CUDAExecutionProvider" in providers

    if requested == "cpu":
        return OCRRuntimeInfo(
            requested_device=requested,
            selected_device="cpu",
            provider="CPUExecutionProvider",
            available_providers=providers,
            cuda_available=cuda_available,
        )

    if cuda_available:
        return OCRRuntimeInfo(
            requested_device=requested,
            selected_device="cuda",
            provider="CUDAExecutionProvider",
            available_providers=providers,
            cuda_available=True,
        )

    reason = "CUDAExecutionProvider is not available"
    if providers:
        reason = f"{reason}; available providers: {', '.join(providers)}"

    return OCRRuntimeInfo(
        requested_device=requested,
        selected_device="cpu",
        provider="CPUExecutionProvider",
        available_providers=providers,
        cuda_available=False,
        fallback_reason=reason if requested in {"auto", "cuda"} else "",
    )


def describe_ocr_runtime(device: str | None = "auto") -> str:
    info = get_ocr_runtime_info(device)
    label = "CUDA" if info.selected_device == "cuda" else "CPU"
    if info.fallback_reason:
        return f"OCR runtime: {label} ({info.fallback_reason})"
    return f"OCR runtime: {label} ({info.provider})"


def _rapidocr_kwargs(selected_device: str) -> dict[str, Any]:
    if selected_device == "cuda":
        return {
            "det_use_cuda": True,
            "cls_use_cuda": True,
            "rec_use_cuda": True,
        }

    # One ONNX Runtime thread per OCR worker avoids CPU oversubscription when
    # several worker threads each own a RapidOCR engine.
    return {
        "intra_op_num_threads": 1,
        "inter_op_num_threads": 1,
    }


def _new_engine(selected_device: str):
    from rapidocr_onnxruntime import RapidOCR  # type: ignore[import-not-found]

    return RapidOCR(**_rapidocr_kwargs(selected_device))


def _thread_cpu_engine():
    engines = getattr(_THREAD_STATE, "rapidocr_engines", None)
    if engines is None:
        engines = {}
        _THREAD_STATE.rapidocr_engines = engines

    key = ("cpu", 1, 1)
    engine = engines.get(key)
    if engine is None:
        engine = _new_engine("cpu")
        engines[key] = engine
    return engine


def _shared_cuda_engine():
    global _CUDA_ENGINE, _CUDA_ENGINE_KEY

    key = ("cuda",)
    if _CUDA_ENGINE is None or _CUDA_ENGINE_KEY != key:
        _CUDA_ENGINE = _new_engine("cuda")
        _CUDA_ENGINE_KEY = key
    return _CUDA_ENGINE


def _run_ocr_engine(engine, photo_path: str):
    result, _elapsed = engine(photo_path)
    return result


def extract_text_candidates(
    photo_path: str,
    backend: str = "none",
    device: str | None = "auto",
) -> list[OCRTextCandidate]:
    """Extract OCR text candidates from an image.

    - ``none``: returns an empty list.
    - ``ocr``: uses RapidOCR when available.
    - any other value: safe no-op.
    """
    if backend not in ("ocr",):
        return []

    info = get_ocr_runtime_info(device)

    try:
        if info.selected_device == "cuda":
            try:
                with _CUDA_LOCK:
                    result = _run_ocr_engine(_shared_cuda_engine(), photo_path)
            except Exception:
                # Provider detection can succeed even when CUDA DLL loading or
                # model initialization fails. Retry once on CPU so OCR remains usable.
                result = _run_ocr_engine(_thread_cpu_engine(), photo_path)
        else:
            result = _run_ocr_engine(_thread_cpu_engine(), photo_path)
    except ImportError:
        return []

    if not result:
        return []

    out: list[OCRTextCandidate] = []
    for item in result:
        if len(item) < 3:
            continue

        poly = item[0]
        text = str(item[1])
        confidence = float(item[2])

        bbox: tuple[int, int, int, int] | None = None
        try:
            xs = [int(p[0]) for p in poly]
            ys = [int(p[1]) for p in poly]
            bbox = (min(xs), min(ys), max(xs), max(ys))
        except Exception:
            pass

        out.append(OCRTextCandidate(text=text, confidence=confidence, bbox=bbox))

    return out
