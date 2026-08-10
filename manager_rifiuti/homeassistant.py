from __future__ import annotations

import httpx

from .models import Collection


def upload(base_url: str, webhook_id: str, year: int, collections: list[Collection]) -> None:
    url = f"{base_url.rstrip('/')}/api/webhook/{webhook_id.strip()}"
    payload = {"year": year, "collections": [item.to_dict() for item in collections]}
    response = httpx.post(url, json=payload, timeout=20)
    response.raise_for_status()
