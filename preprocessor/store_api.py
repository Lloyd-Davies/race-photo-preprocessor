"""race-photo-store admin API client."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


# ── Helpers ───────────────────────────────────────────────────────────────────

def _base(url: str) -> str:
    """Normalise a store URL: ensure scheme, strip trailing slash."""
    url = url.strip()
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.rstrip("/")


def _headers(token: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Admin-Token": token,
    }


def _user_error(exc: Exception) -> str:
    """Convert an httpx or network exception into a readable message."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 401:
            return "Unauthorised — check your admin token."
        if code == 403:
            return "Forbidden — token does not have admin access."
        if code == 404:
            return "Not found — check the store URL."
        return f"Server returned {code}."
    if isinstance(exc, httpx.ConnectError):
        return "Could not connect — check the URL and that the store is reachable."
    if isinstance(exc, httpx.TimeoutException):
        return "Connection timed out — store may be unreachable or slow."
    return str(exc)


# ── Connection test ───────────────────────────────────────────────────────────

@dataclass
class ConnectionResult:
    ok: bool
    message: str
    stats: dict[str, Any] | None = None


def test_connection(base_url: str, token: str) -> ConnectionResult:
    """Hit GET /api/admin/stats to verify URL + token in one call."""
    if not base_url or not token:
        return ConnectionResult(ok=False, message="Store URL and admin token are required.")
    url = f"{_base(base_url)}/api/admin/stats"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=_headers(token))
            resp.raise_for_status()
            stats = resp.json()
        events = stats.get("total_events", "?")
        photos = stats.get("total_photos", "?")
        return ConnectionResult(
            ok=True,
            message=f"Connected — {events} event(s), {photos} photo(s).",
            stats=stats,
        )
    except Exception as exc:
        return ConnectionResult(ok=False, message=_user_error(exc))


# ── Events ────────────────────────────────────────────────────────────────────

def list_events(base_url: str, token: str) -> list[dict[str, Any]]:
    url = f"{_base(base_url)}/api/events"
    with httpx.Client(timeout=20.0) as client:
        resp = client.get(url, headers=_headers(token))
        resp.raise_for_status()
        data = resp.json()
    return data if isinstance(data, list) else []


def find_event_id_by_slug(base_url: str, token: str, slug: str) -> int | None:
    try:
        events = list_events(base_url, token)
    except Exception:
        return None
    for event in events:
        if str(event.get("slug", "")).strip().lower() == slug.strip().lower():
            try:
                return int(event["id"])
            except Exception:
                return None
    return None


# ── Bib tags ──────────────────────────────────────────────────────────────────

def upload_bib_tags(
    base_url: str,
    token: str,
    event_id: int,
    tags: list[dict[str, Any]],
) -> dict[str, Any]:
    url = f"{_base(base_url)}/api/admin/events/{event_id}/tags/bibs"
    payload = {"tags": tags}
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, headers=_headers(token), json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data if isinstance(data, dict) else {"added": 0}


# ── Photo upload ──────────────────────────────────────────────────────────────

def upload_photo(
    base_url: str,
    token: str,
    event_id: int,
    photo_id: str,
    kind: str,
    file_path: Path,
) -> dict[str, Any]:
    """Upload one image file (kind='original' or 'proof') to the store.

    Uses multipart/form-data. Content-Type is NOT set in auth headers so
    httpx can inject the correct multipart boundary automatically.
    """
    url = f"{_base(base_url)}/api/admin/events/{event_id}/photos"
    auth_header = {"X-Admin-Token": token}
    with file_path.open("rb") as fh:
        resp_data: dict[str, Any] = {}
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                url,
                headers=auth_header,
                data={"photo_id": photo_id, "kind": kind},
                files={"file": (file_path.name, fh, "image/jpeg")},
            )
            resp.raise_for_status()
            resp_data = resp.json()
    return resp_data if isinstance(resp_data, dict) else {}
