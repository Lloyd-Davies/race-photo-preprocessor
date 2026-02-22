from __future__ import annotations

import httpx
import pytest

from preprocessor.store_api import (
    find_event_id_by_slug,
    get_uploaded_photo_ids,
    list_admin_events,
    list_events,
    upload_bib_tags,
)


def test_list_events() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/events"
        return httpx.Response(200, json=[{"id": 1, "slug": "race-a"}])

    transport = httpx.MockTransport(handler)

    original_client = httpx.Client

    class _Client(httpx.Client):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    httpx.Client = _Client  # type: ignore[assignment]
    try:
        events = list_events("http://local", "token")
    finally:
        httpx.Client = original_client  # type: ignore[assignment]

    assert events == [{"id": 1, "slug": "race-a"}]


def test_find_event_id_by_slug() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": 10, "slug": "spring-run"}, {"id": 11, "slug": "night-race"}])

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    class _Client(httpx.Client):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    httpx.Client = _Client  # type: ignore[assignment]
    try:
        event_id = find_event_id_by_slug("http://local", "token", "night-race")
    finally:
        httpx.Client = original_client  # type: ignore[assignment]

    assert event_id == 11


def test_upload_bib_tags() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/admin/events/11/tags/bibs"
        payload = request.read().decode("utf-8")
        assert "IMG_001" in payload
        return httpx.Response(200, json={"added": 2})

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    class _Client(httpx.Client):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    httpx.Client = _Client  # type: ignore[assignment]
    try:
        out = upload_bib_tags(
            "http://local",
            "token",
            event_id=11,
            tags=[
                {"photo_id": "IMG_001", "bib": "465", "confidence": 0.99},
                {"photo_id": "IMG_002", "bib": "469", "confidence": 0.92},
            ],
        )
    finally:
        httpx.Client = original_client  # type: ignore[assignment]

    assert out["added"] == 2


# ── list_admin_events ─────────────────────────────────────────────────────────

def _mock_client(handler):
    """Return a patched httpx.Client class that routes through *handler*."""
    transport = httpx.MockTransport(handler)

    class _Client(httpx.Client):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    return _Client


def test_list_admin_events() -> None:
    """list_admin_events hits /api/admin/events and sends the auth header."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/admin/events"
        assert request.headers.get("X-Admin-Token") == "secret"
        return httpx.Response(200, json=[{"id": 1, "slug": "race-a"}, {"id": 2, "slug": "race-b"}])

    original = httpx.Client
    httpx.Client = _mock_client(handler)  # type: ignore[assignment]
    try:
        events = list_admin_events("http://local", "secret")
    finally:
        httpx.Client = original  # type: ignore[assignment]

    assert [e["slug"] for e in events] == ["race-a", "race-b"]


def test_find_event_id_by_slug_uses_admin_endpoint_first() -> None:
    """find_event_id_by_slug uses the admin endpoint (which includes archived events)."""
    paths_called: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths_called.append(request.url.path)
        return httpx.Response(200, json=[{"id": 7, "slug": "spring-run"}])

    original = httpx.Client
    httpx.Client = _mock_client(handler)  # type: ignore[assignment]
    try:
        event_id = find_event_id_by_slug("http://local", "token", "spring-run")
    finally:
        httpx.Client = original  # type: ignore[assignment]

    assert event_id == 7
    # Admin endpoint was tried first and succeeded — public endpoint not needed
    assert "/api/admin/events" in paths_called
    assert paths_called[0] == "/api/admin/events"


def test_find_event_id_by_slug_falls_back_to_public() -> None:
    """When the admin endpoint fails (e.g. non-admin token), public list is tried."""
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if request.url.path == "/api/admin/events":
            return httpx.Response(403, text="Forbidden")
        # public /api/events fallback
        return httpx.Response(200, json=[{"id": 5, "slug": "night-race"}])

    original = httpx.Client
    httpx.Client = _mock_client(handler)  # type: ignore[assignment]
    try:
        event_id = find_event_id_by_slug("http://local", "token", "night-race")
    finally:
        httpx.Client = original  # type: ignore[assignment]

    assert event_id == 5
    assert call_count["n"] == 2  # admin tried first, then public


def test_find_event_id_by_slug_returns_none_when_both_fail() -> None:
    """Returns None when both admin and public endpoints fail."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="error")

    original = httpx.Client
    httpx.Client = _mock_client(handler)  # type: ignore[assignment]
    try:
        event_id = find_event_id_by_slug("http://local", "token", "no-event")
    finally:
        httpx.Client = original  # type: ignore[assignment]

    assert event_id is None


# ── get_uploaded_photo_ids ────────────────────────────────────────────────────

def test_get_uploaded_photo_ids() -> None:
    """Returns the set of photo_ids from the admin photo_ids endpoint."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/admin/events/42/photo_ids"
        assert request.headers.get("X-Admin-Token") == "tok"
        return httpx.Response(200, json={"photo_ids": ["img001", "img002", "img003"]})

    original = httpx.Client
    httpx.Client = _mock_client(handler)  # type: ignore[assignment]
    try:
        ids = get_uploaded_photo_ids("http://local", "tok", 42)
    finally:
        httpx.Client = original  # type: ignore[assignment]

    assert ids == {"img001", "img002", "img003"}


def test_get_uploaded_photo_ids_returns_empty_on_error() -> None:
    """Returns an empty set when the endpoint is unreachable or returns an error."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Not found")

    original = httpx.Client
    httpx.Client = _mock_client(handler)  # type: ignore[assignment]
    try:
        ids = get_uploaded_photo_ids("http://local", "tok", 99)
    finally:
        httpx.Client = original  # type: ignore[assignment]

    assert ids == set()


def test_get_uploaded_photo_ids_returns_empty_on_connect_error() -> None:
    """Returns an empty set on network-level errors (never raises)."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable")

    original = httpx.Client
    httpx.Client = _mock_client(handler)  # type: ignore[assignment]
    try:
        ids = get_uploaded_photo_ids("http://local", "tok", 1)
    finally:
        httpx.Client = original  # type: ignore[assignment]

    assert ids == set()
