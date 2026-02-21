from __future__ import annotations

import httpx

from preprocessor.store_api import find_event_id_by_slug, list_events, upload_bib_tags


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
