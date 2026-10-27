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
    def __init__(self, interval: float, headers: dict[str, str] | None = None):
        self.interval = interval
        self.client = httpx.Client(headers=headers, timeout=30, follow_redirects=True)
        self._last = 0.0

    def get_json(self, url: str, params: dict | None = None) -> dict:
        delay = self.interval - (time.monotonic() - self._last)
        if delay > 0:
            time.sleep(delay)
        response = self.client.get(url, params=params)
        self._last = time.monotonic()
        response.raise_for_status()
        return response.json()

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
