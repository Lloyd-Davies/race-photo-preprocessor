"""race-photo-store admin API client."""
from __future__ import annotations

from typing import Any

import httpx


def _headers(token: str) -> dict[str, str]:
	return {
		"Content-Type": "application/json",
		"X-Admin-Token": token,
	}


def list_events(base_url: str, token: str) -> list[dict[str, Any]]:
	url = f"{base_url.rstrip('/')}/api/events"
	with httpx.Client(timeout=20.0) as client:
		resp = client.get(url, headers=_headers(token))
		resp.raise_for_status()
		data = resp.json()
	if isinstance(data, list):
		return data
	return []


def find_event_id_by_slug(base_url: str, token: str, slug: str) -> int | None:
	events = list_events(base_url, token)
	for event in events:
		if str(event.get("slug", "")).strip().lower() == slug.strip().lower():
			try:
				return int(event["id"])
			except Exception:
				return None
	return None


def upload_bib_tags(
	base_url: str,
	token: str,
	event_id: int,
	tags: list[dict[str, Any]],
) -> dict[str, Any]:
	url = f"{base_url.rstrip('/')}/api/admin/events/{event_id}/tags/bibs"
	payload = {"tags": tags}
	with httpx.Client(timeout=30.0) as client:
		resp = client.post(url, headers=_headers(token), json=payload)
		resp.raise_for_status()
		data = resp.json()

	if isinstance(data, dict):
		return data
	return {"added": 0}
