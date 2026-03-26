from __future__ import annotations

import httpx

def read_json(response: httpx.Response) -> dict[str, object]:
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError(f"Expected JSON object response, got {payload!r}")
    return payload
