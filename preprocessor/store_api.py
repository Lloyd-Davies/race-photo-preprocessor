"""race-photo-store admin API client."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
import time
from typing import Any, Literal

import httpx


_RATE_LIMIT_MAX_RETRIES = 6
_RATE_LIMIT_BASE_DELAY_SECONDS = 0.5
_THREAD_AUTH = threading.local()
_THREAD_CLIENT = threading.local()


def _get_thread_client(timeout: float = 120.0) -> httpx.Client:
    """Return a long-lived per-thread httpx.Client, creating one when needed.

    Reusing a single client per thread keeps the underlying TCP+TLS connection
    alive between photo uploads, which eliminates per-request handshake overhead
    and dramatically reduces latency for bulk uploads.
    """
    client: httpx.Client | None = getattr(_THREAD_CLIENT, "http_client", None)
    if client is None or client.is_closed:
        client = httpx.Client(timeout=timeout)
        _THREAD_CLIENT.http_client = client
    return client


def _close_thread_client_for_tests() -> None:
    """Test helper: close and discard the per-thread client."""
    client: httpx.Client | None = getattr(_THREAD_CLIENT, "http_client", None)
    if client is not None and not client.is_closed:
        try:
            client.close()
        except Exception:
            pass
    _THREAD_CLIENT.http_client = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _base(url: str) -> str:
    """Normalise a store URL: ensure scheme, strip trailing slash."""
    url = url.strip()
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.rstrip("/")


@dataclass
class _AuthContext:
    mode: Literal["session", "legacy"]
    credential: str
    access_token: str | None = None
    refresh_token: str | None = None


def _auth_headers(ctx: _AuthContext, *, include_content_type: bool = True) -> dict[str, str]:
    headers: dict[str, str] = {}
    if include_content_type:
        headers["Content-Type"] = "application/json"

    if ctx.mode == "session" and ctx.access_token:
        headers["Authorization"] = f"Bearer {ctx.access_token}"
        return headers

    headers["X-Admin-Token"] = ctx.credential
    return headers


def _thread_auth_key(base_url: str, credential: str) -> str:
    return f"{_base(base_url)}|{credential}"


def _thread_auth_get(base_url: str, credential: str) -> _AuthContext | None:
    cache = getattr(_THREAD_AUTH, "cache", None)
    if not isinstance(cache, dict):
        return None
    return cache.get(_thread_auth_key(base_url, credential))


def _thread_auth_set(base_url: str, credential: str, ctx: _AuthContext) -> None:
    cache = getattr(_THREAD_AUTH, "cache", None)
    if not isinstance(cache, dict):
        cache = {}
        _THREAD_AUTH.cache = cache
    cache[_thread_auth_key(base_url, credential)] = ctx


def _thread_auth_clear(base_url: str, credential: str) -> None:
    cache = getattr(_THREAD_AUTH, "cache", None)
    if isinstance(cache, dict):
        cache.pop(_thread_auth_key(base_url, credential), None)


def _clear_thread_auth_cache_for_tests() -> None:
    """Test helper: clear in-thread auth cache to avoid cross-test bleed."""
    cache = getattr(_THREAD_AUTH, "cache", None)
    if isinstance(cache, dict):
        cache.clear()


def _refresh_session(client: httpx.Client, base_url: str, ctx: _AuthContext) -> bool:
    if ctx.mode != "session" or not ctx.refresh_token:
        return False

    resp = client.post(
        f"{_base(base_url)}/api/admin/refresh",
        json={"refresh_token": ctx.refresh_token},
        headers={"Content-Type": "application/json"},
    )
    if resp.status_code >= 400:
        return False

    data = resp.json() if resp.content else {}
    ctx.access_token = str(data.get("access_token", "") or "")
    ctx.refresh_token = str(data.get("refresh_token", "") or "")
    return bool(ctx.access_token)


def _authenticate(
    client: httpx.Client,
    base_url: str,
    credential: str,
    *,
    use_thread_cache: bool = False,
) -> _AuthContext:
    if use_thread_cache:
        cached = _thread_auth_get(base_url, credential)
        if cached is not None:
            return cached

    # New auth flow: login -> bearer session tokens.
    login = client.post(
        f"{_base(base_url)}/api/admin/login",
        json={"admin_token": credential},
        headers={"Content-Type": "application/json"},
    )

    # Backward-compat fallback for older server deployments.
    if login.status_code == 404:
        ctx = _AuthContext(mode="legacy", credential=credential)
        if use_thread_cache:
            _thread_auth_set(base_url, credential, ctx)
        return ctx

    login.raise_for_status()
    body = login.json() if login.content else {}
    access_token = str(body.get("access_token", "") or "")
    refresh_token = str(body.get("refresh_token", "") or "")
    if not access_token:
        raise RuntimeError("Admin login succeeded but did not return an access token.")

    ctx = _AuthContext(
        mode="session",
        credential=credential,
        access_token=access_token,
        refresh_token=refresh_token,
    )
    if use_thread_cache:
        _thread_auth_set(base_url, credential, ctx)
    return ctx


def _retry_after_seconds(resp: httpx.Response, attempt: int) -> float:
    header = (resp.headers.get("Retry-After") or "").strip()
    if header:
        try:
            parsed = float(header)
            if parsed >= 0:
                return parsed
        except Exception:
            pass
    return _RATE_LIMIT_BASE_DELAY_SECONDS * (2 ** attempt)


def _rewind_files(files: Any) -> None:
    if not isinstance(files, dict):
        return
    for value in files.values():
        file_obj = None
        if isinstance(value, tuple) and len(value) >= 2:
            file_obj = value[1]
        if hasattr(file_obj, "seek"):
            try:
                file_obj.seek(0)
            except Exception:
                pass


def _request_authed(
    client: httpx.Client,
    base_url: str,
    ctx: _AuthContext,
    method: str,
    path: str,
    *,
    include_content_type: bool = True,
    **kwargs: Any,
) -> httpx.Response:
    url = f"{_base(base_url)}{path}"
    base_headers = dict(kwargs.pop("headers", {}) or {})

    retried_auth = False
    retry_429 = 0

    while True:
        _rewind_files(kwargs.get("files"))
        headers = dict(base_headers)
        headers.update(_auth_headers(ctx, include_content_type=include_content_type))

        resp = client.request(method, url, headers=headers, **kwargs)

        if resp.status_code == 401 and ctx.mode == "session" and not retried_auth:
            retried_auth = True
            if _refresh_session(client, base_url, ctx):
                continue
            _thread_auth_clear(base_url, ctx.credential)

        if resp.status_code == 429 and retry_429 < _RATE_LIMIT_MAX_RETRIES:
            delay = _retry_after_seconds(resp, retry_429)
            retry_429 += 1
            time.sleep(delay)
            continue

        resp.raise_for_status()
        return resp


def _user_error(exc: Exception) -> str:
    """Convert an httpx or network exception into a readable message."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 401:
            return "Unauthorised — check your admin credential."
        if code == 429:
            return "Rate limited by server — lower upload connections and retry."
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
    """Verify URL + admin credential using session login flow when available."""
    if not base_url or not token:
        return ConnectionResult(ok=False, message="Store URL and admin credential are required.")

    try:
        with httpx.Client(timeout=10.0) as client:
            ctx = _authenticate(client, base_url, token)
            if ctx.mode == "session":
                resp = _request_authed(client, base_url, ctx, "GET", "/api/admin/session")
                stats = {"ok": resp.status_code == 200}
                return ConnectionResult(ok=True, message="Connected — admin session ready.", stats=stats)

            # Legacy fallback
            resp = _request_authed(client, base_url, ctx, "GET", "/api/admin/stats")
            stats = resp.json() if resp.content else {}
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
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
    return data if isinstance(data, list) else []


def list_admin_events(base_url: str, token: str) -> list[dict[str, Any]]:
    """Return all events (any status) via the admin endpoint."""
    with httpx.Client(timeout=20.0) as client:
        ctx = _authenticate(client, base_url, token)
        resp = _request_authed(client, base_url, ctx, "GET", "/api/admin/events")
        data = resp.json()
    return data if isinstance(data, list) else []


def find_event_id_by_slug(base_url: str, token: str, slug: str) -> int | None:
    """Look up an event by slug; tries the admin endpoint first (returns all
    statuses), falls back to the public events list on error."""
    for fetch in (list_admin_events, list_events):
        try:
            events = fetch(base_url, token)
            for event in events:
                if str(event.get("slug", "")).strip().lower() == slug.strip().lower():
                    try:
                        return int(event["id"])
                    except Exception:
                        return None
        except Exception:
            continue
    return None


# ── Bib tags ──────────────────────────────────────────────────────────────────

def get_uploaded_photo_ids(base_url: str, token: str, event_id: int) -> set[str]:
    """Return the set of photo_id stems already on the store for *event_id*."""
    try:
        with httpx.Client(timeout=20.0) as client:
            ctx = _authenticate(client, base_url, token)
            resp = _request_authed(client, base_url, ctx, "GET", f"/api/admin/events/{event_id}/photo_ids")
            data = resp.json()
        return set(data.get("photo_ids", []))
    except Exception:
        return set()


def upload_bib_tags(
    base_url: str,
    token: str,
    event_id: int,
    tags: list[dict[str, Any]],
    replace: bool = False,
) -> dict[str, Any]:
    payload = {"tags": tags, "replace": replace}
    with httpx.Client(timeout=60.0) as client:
        ctx = _authenticate(client, base_url, token)
        resp = _request_authed(
            client,
            base_url,
            ctx,
            "POST",
            f"/api/admin/events/{event_id}/tags/bibs",
            json=payload,
        )
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

    The underlying httpx.Client is kept alive for the lifetime of the calling
    thread (via _get_thread_client) so that TCP/TLS connections are reused
    across sequential uploads within the same worker thread, avoiding
    per-request handshake overhead during bulk operations.
    """
    with file_path.open("rb") as fh:
        client = _get_thread_client(timeout=120.0)
        ctx = _authenticate(client, base_url, token, use_thread_cache=True)
        resp = _request_authed(
            client,
            base_url,
            ctx,
            "POST",
            f"/api/admin/events/{event_id}/photos",
            include_content_type=False,
            data={"photo_id": photo_id, "kind": kind},
            files={"file": (file_path.name, fh, "image/jpeg")},
        )
        resp_data = resp.json()
    return resp_data if isinstance(resp_data, dict) else {}
