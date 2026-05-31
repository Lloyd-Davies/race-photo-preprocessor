from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from preprocessor import bib_ocr


def test_ocr_runtime_auto_uses_cuda_when_provider_available(monkeypatch) -> None:
    monkeypatch.setattr(
        bib_ocr,
        "_available_onnx_providers",
        lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"],
    )

    info = bib_ocr.get_ocr_runtime_info("auto")

    assert info.selected_device == "cuda"
    assert info.provider == "CUDAExecutionProvider"
    assert info.fallback_reason == ""


def test_ocr_runtime_cuda_falls_back_when_provider_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        bib_ocr,
        "_available_onnx_providers",
        lambda: ["CPUExecutionProvider"],
    )

    info = bib_ocr.get_ocr_runtime_info("cuda")

    assert info.selected_device == "cpu"
    assert info.provider == "CPUExecutionProvider"
    assert "CUDAExecutionProvider is not available" in info.fallback_reason


def test_ocr_runtime_cpu_forces_cpu_even_when_cuda_available(monkeypatch) -> None:
    monkeypatch.setattr(
        bib_ocr,
        "_available_onnx_providers",
        lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"],
    )

    info = bib_ocr.get_ocr_runtime_info("cpu")

    assert info.selected_device == "cpu"
    assert info.fallback_reason == ""


def test_cpu_ocr_uses_thread_local_engines(monkeypatch) -> None:
    monkeypatch.setattr(
        bib_ocr,
        "_available_onnx_providers",
        lambda: ["CPUExecutionProvider"],
    )

    barrier = threading.Barrier(2)
    created_thread_ids: set[int] = set()
    lock = threading.Lock()

    class FakeEngine:
        def __call__(self, _photo_path: str):
            barrier.wait(timeout=5)
            return [([[0, 0], [1, 0], [1, 1], [0, 1]], "123", 0.9)], 0.0

    def fake_new_engine(selected_device: str):
        assert selected_device == "cpu"
        with lock:
            created_thread_ids.add(threading.get_ident())
        return FakeEngine()

    monkeypatch.setattr(bib_ocr, "_new_engine", fake_new_engine)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(bib_ocr.extract_text_candidates, "a.jpg", backend="ocr", device="cpu"),
            executor.submit(bib_ocr.extract_text_candidates, "b.jpg", backend="ocr", device="cpu"),
        ]
        results = [future.result(timeout=5) for future in futures]

    assert len(created_thread_ids) == 2
    assert [[candidate.text for candidate in result] for result in results] == [["123"], ["123"]]
