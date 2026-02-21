"""Background worker for store API deployment."""
from __future__ import annotations

import csv
from pathlib import Path

import preprocessor.config as cfg
from preprocessor import store_api

from PySide6.QtCore import QThread, Signal


class DeployWorker(QThread):
    """Uploads photos and/or bib tags to the race-photo-store.

    Signals
    -------
    progress(current, total, label)
        Fired before each file/step so the UI can update the progress bar.
    log(message)
        Human-readable status line for the log panel.
    finished(success, message)
        Fired once when the run completes or is aborted.
    """

    progress: Signal = Signal(int, int, str)   # current, total, label
    log: Signal = Signal(str)                  # log line
    finished: Signal = Signal(bool, str)       # success, message

    def __init__(
        self,
        *,
        upload_originals: bool = True,
        upload_proofs: bool = True,
        upload_bibs: bool = True,
        replace_bibs: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._upload_originals = upload_originals
        self._upload_proofs = upload_proofs
        self._upload_bibs = upload_bibs
        self._replace_bibs = replace_bibs
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _emit_log(self, msg: str) -> None:
        self.log.emit(msg)

    def _check_stop(self) -> bool:
        if self._stop:
            self.finished.emit(False, "Cancelled by user.")
        return self._stop

    # ── Main run ──────────────────────────────────────────────────────────────

    def run(self) -> None:
        base_url = cfg.get_store_url()
        token = cfg.get_store_token()
        slug = cfg.get_event_slug()
        output_root = cfg.get_output_root()

        if not base_url or not token:
            self.finished.emit(False, "Store URL and admin token are required — set them in the sidebar.")
            return
        if not slug:
            self.finished.emit(False, "Event slug is required — set it in the sidebar.")
            return
        if not output_root:
            self.finished.emit(False, "Output root is required — set it in the sidebar.")
            return

        root = Path(output_root)
        originals_dir = root / "originals" / slug
        proofs_dir = root / "proofs" / slug
        bibs_csv = root / "bibs" / slug / "bib_tags.csv"

        # ── Resolve event ID ──────────────────────────────────────────────────
        self._emit_log("Looking up event in store…")
        event_id = store_api.find_event_id_by_slug(base_url, token, slug)
        if event_id is None:
            self.finished.emit(
                False,
                f"Event '{slug}' not found in the store. Create it first via the store admin.",
            )
            return
        self._emit_log(f"Event ID: {event_id}")

        # ── Collect files ─────────────────────────────────────────────────────
        originals = sorted(originals_dir.glob("*.jpg")) if (self._upload_originals and originals_dir.exists()) else []
        proofs = sorted(proofs_dir.glob("*.jpg")) if (self._upload_proofs and proofs_dir.exists()) else []

        bib_rows: list[dict] = []
        if self._upload_bibs and bibs_csv.exists():
            try:
                with bibs_csv.open("r", encoding="utf-8", newline="") as f:
                    bib_rows = list(csv.DictReader(f))
            except Exception as exc:
                self._emit_log(f"Warning: could not read bib CSV — {exc}")

        total = len(originals) + len(proofs) + (1 if bib_rows else 0)
        if total == 0:
            self.finished.emit(False, "Nothing to upload — check your selections and output folder.")
            return

        current = 0

        # ── Upload originals ──────────────────────────────────────────────────
        errors = 0
        for path in originals:
            if self._check_stop():
                return
            photo_id = path.stem
            self.progress.emit(current, total, f"Uploading original: {photo_id}")
            try:
                store_api.upload_photo(base_url, token, event_id, photo_id, "original", path)
                self._emit_log(f"  ✔ original {photo_id}")
            except Exception as exc:
                self._emit_log(f"  ✖ original {photo_id} — {store_api._user_error(exc)}")
                errors += 1
            current += 1

        # ── Upload proofs ─────────────────────────────────────────────────────
        for path in proofs:
            if self._check_stop():
                return
            photo_id = path.stem
            self.progress.emit(current, total, f"Uploading proof: {photo_id}")
            try:
                store_api.upload_photo(base_url, token, event_id, photo_id, "proof", path)
                self._emit_log(f"  ✔ proof {photo_id}")
            except Exception as exc:
                self._emit_log(f"  ✖ proof {photo_id} — {store_api._user_error(exc)}")
                errors += 1
            current += 1

        # ── Upload bib tags ───────────────────────────────────────────────────
        if bib_rows:
            if self._check_stop():
                return
            self.progress.emit(current, total, f"Uploading {len(bib_rows)} bib tag(s)…")
            try:
                payload = [
                    {
                        "photo_id": r["photo_id"],
                        "bib": r["bib"],
                        "confidence": float(r.get("confidence", 1.0)),
                    }
                    for r in bib_rows
                ]
                result = store_api.upload_bib_tags(base_url, token, event_id, payload, replace=self._replace_bibs)
                added = result.get("added", "?")
                self._emit_log(f"  ✔ bib tags — {added} added")
            except Exception as exc:
                self._emit_log(f"  ✖ bib tags — {store_api._user_error(exc)}")
                errors += 1
            current += 1

        self.progress.emit(total, total, "Done")
        if errors:
            self.finished.emit(False, f"Completed with {errors} error(s) — see log above.")
        else:
            self.finished.emit(True, f"Upload complete — {total} step(s), 0 errors.")
