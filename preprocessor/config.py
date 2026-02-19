"""QSettings-backed typed config store."""
from __future__ import annotations

from PySide6.QtCore import QSettings

_ORG = "RacePhotoStore"
_APP = "Preprocessor"


def _s() -> QSettings:
    return QSettings(_ORG, _APP)


# ── Event ─────────────────────────────────────────────────────────────────────

def get_event_slug() -> str:
    return str(_s().value("event/slug", ""))

def set_event_slug(v: str) -> None:
    _s().setValue("event/slug", v)

def get_event_name() -> str:
    return str(_s().value("event/name", ""))

def set_event_name(v: str) -> None:
    _s().setValue("event/name", v)


# ── Output ────────────────────────────────────────────────────────────────────

def get_output_root() -> str:
    return str(_s().value("output/root", ""))

def set_output_root(v: str) -> None:
    _s().setValue("output/root", v)


# ── Store API ─────────────────────────────────────────────────────────────────

def get_store_url() -> str:
    return str(_s().value("store/url", "http://localhost:8081"))

def set_store_url(v: str) -> None:
    _s().setValue("store/url", v)

def get_store_token() -> str:
    return str(_s().value("store/token", ""))

def set_store_token(v: str) -> None:
    _s().setValue("store/token", v)


# ── SFTP ──────────────────────────────────────────────────────────────────────

def get_sftp_host() -> str:
    return str(_s().value("sftp/host", ""))

def set_sftp_host(v: str) -> None:
    _s().setValue("sftp/host", v)

def get_sftp_port() -> int:
    return int(_s().value("sftp/port", 22))  # type: ignore[arg-type]

def set_sftp_port(v: int) -> None:
    _s().setValue("sftp/port", v)

def get_sftp_username() -> str:
    return str(_s().value("sftp/username", ""))

def set_sftp_username(v: str) -> None:
    _s().setValue("sftp/username", v)

def get_sftp_key_path() -> str:
    return str(_s().value("sftp/key_path", ""))

def set_sftp_key_path(v: str) -> None:
    _s().setValue("sftp/key_path", v)

def get_sftp_remote_path() -> str:
    return str(_s().value("sftp/remote_path", "/mnt/pstore/photos"))

def set_sftp_remote_path(v: str) -> None:
    _s().setValue("sftp/remote_path", v)


# ── Watermark ─────────────────────────────────────────────────────────────────

def get_watermark_text() -> str:
    return str(_s().value("watermark/text", "© Race Photos"))

def set_watermark_text(v: str) -> None:
    _s().setValue("watermark/text", v)

def get_watermark_opacity() -> int:
    return int(_s().value("watermark/opacity", 85))  # type: ignore[arg-type]

def set_watermark_opacity(v: int) -> None:
    _s().setValue("watermark/opacity", v)

def get_watermark_position() -> str:
    return str(_s().value("watermark/position", "bottom-right"))

def set_watermark_position(v: str) -> None:
    _s().setValue("watermark/position", v)


# ── Processing ────────────────────────────────────────────────────────────────

def get_proof_size() -> int:
    return int(_s().value("process/proof_size", 1600))  # type: ignore[arg-type]

def set_proof_size(v: int) -> None:
    _s().setValue("process/proof_size", v)

def get_proof_quality() -> int:
    return int(_s().value("process/proof_quality", 82))  # type: ignore[arg-type]

def set_proof_quality(v: int) -> None:
    _s().setValue("process/proof_quality", v)

def get_skip_existing() -> bool:
    return _s().value("process/skip_existing", True, type=bool)  # type: ignore[call-overload]

def set_skip_existing(v: bool) -> None:
    _s().setValue("process/skip_existing", v)


# ── Last used import folder ───────────────────────────────────────────────────

def get_last_import_folder() -> str:
    return str(_s().value("import/last_folder", ""))

def set_last_import_folder(v: str) -> None:
    _s().setValue("import/last_folder", v)
