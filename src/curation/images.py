import hashlib
import time
from pathlib import Path

import httpx

from .models import Candidate


def image_path(cache: Path, item: Candidate) -> Path:
    suffix = Path(str(item.image.url).split("?", 1)[0]).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    return cache / f"{item.id}-{hashlib.sha256(str(item.image.url).encode()).hexdigest()[:10]}{suffix}"


def fetch_images(items: list[Candidate], cache: Path, interval: float = 1.0) -> tuple[int, int]:
    cache.mkdir(parents=True, exist_ok=True)
    fetched = skipped = 0
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for item in items:
            target = image_path(cache, item)
            if target.exists() and target.stat().st_size:
                skipped += 1
                continue
            response = client.get(str(item.image.url))
            response.raise_for_status()
            tmp = target.with_suffix(target.suffix + ".part")
            tmp.write_bytes(response.content)
            tmp.replace(target)
            fetched += 1
            if interval:
                time.sleep(interval)
    return fetched, skipped
