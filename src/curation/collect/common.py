import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from ..models import Candidate


@dataclass
class CollectionResult:
    items: list[Candidate] = field(default_factory=list)
    skipped_existing: int = 0
    rejected: int = 0
    duplicates: int = 0
    scanned: int = 0
    queries: list[str] = field(default_factory=list)


DEFAULT_QUERIES = {
    "aic": ["landscape seascape cityscape sky"],
    "met": ["landscape", "sky", "seascape", "cityscape", "weather"],
    "cma": ["landscape", "sky", "cloud", "weather", "rain", "snow", "fog", "storm", "seascape", "cityscape"],
}


class RateClient:
    def __init__(self, interval: float, headers: dict[str, str] | None = None, max_attempts: int = 3):
        self.interval = interval
        default_headers = {"User-Agent": "weather-art-curation/0.1", "Accept": "application/json"}
        self.client = httpx.Client(headers={**default_headers, **(headers or {})}, timeout=30, follow_redirects=True)
        self.max_attempts = max_attempts
        self._last = 0.0

    def get_json(self, url: str, params: dict | None = None) -> dict:
        for attempt in range(self.max_attempts):
            delay = self.interval - (time.monotonic() - self._last)
            if delay > 0:
                time.sleep(delay)
            try:
                response = self.client.get(url, params=params)
                self._last = time.monotonic()
                if response.status_code != 429 and response.status_code < 500:
                    response.raise_for_status()
                    return response.json()
                if attempt == self.max_attempts - 1:
                    response.raise_for_status()
                retry_after = response.headers.get("Retry-After")
                backoff = float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else 0.5 * (2**attempt)
                time.sleep(min(backoff, 30.0))
            except httpx.TransportError:
                self._last = time.monotonic()
                if attempt == self.max_attempts - 1:
                    raise
                time.sleep(0.5 * (2**attempt))
        raise RuntimeError("unreachable")

    def close(self):
        self.client.close()


def limited(items, limit: int, transform: Callable):
    result = []
    for item in items:
        if len(result) >= limit:
            break
        value = transform(item)
        if value is not None:
            result.append(value)
    return result
