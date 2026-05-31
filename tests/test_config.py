from __future__ import annotations

import preprocessor.config as cfg


def test_proof_and_ocr_worker_settings_are_independent() -> None:
    old_legacy = cfg.get_worker_count()
    old_proof = cfg.get_proof_worker_count()
    old_ocr = cfg.get_ocr_worker_count()
    old_device = cfg.get_ocr_device()
    old_jpeg_mode = cfg.get_proof_jpeg_mode()

    try:
        cfg.set_worker_count(7)
        cfg.set_proof_worker_count(2)
        cfg.set_ocr_worker_count(3)
        cfg.set_ocr_device("cuda")
        cfg.set_proof_jpeg_mode("compat")

        assert cfg.get_worker_count() == 7
        assert cfg.get_proof_worker_count() == 2
        assert cfg.get_ocr_worker_count() == 3
        assert cfg.get_ocr_device() == "cuda"
        assert cfg.get_proof_jpeg_mode() == "compat"
    finally:
        cfg.set_worker_count(old_legacy)
        cfg.set_proof_worker_count(old_proof)
        cfg.set_ocr_worker_count(old_ocr)
        cfg.set_ocr_device(old_device)
        cfg.set_proof_jpeg_mode(old_jpeg_mode)


def test_invalid_runtime_settings_fall_back_to_defaults() -> None:
    old_device = cfg.get_ocr_device()
    old_jpeg_mode = cfg.get_proof_jpeg_mode()

    try:
        cfg.set_ocr_device("invalid")
        cfg.set_proof_jpeg_mode("invalid")

        assert cfg.get_ocr_device() == "auto"
        assert cfg.get_proof_jpeg_mode() == "fast"
    finally:
        cfg.set_ocr_device(old_device)
        cfg.set_proof_jpeg_mode(old_jpeg_mode)
