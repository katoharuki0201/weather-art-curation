import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from .models import Candidate


@dataclass(frozen=True)
class ImageFailure:
    id: str
    reason: str


@dataclass
class FetchResult:
    fetched: int = 0
    skipped: int = 0
    failures: list[ImageFailure] = field(default_factory=list)

    @property
    def failed(self) -> int:
        return len(self.failures)


def image_path(cache: Path, item: Candidate) -> Path:
    suffix = Path(str(item.image.url).split("?", 1)[0]).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    return cache / f"{item.id}-{hashlib.sha256(str(item.image.url).encode()).hexdigest()[:10]}{suffix}"


def fetch_images(items: list[Candidate], cache: Path, interval: float = 1.0, aic_contact: str | None = None) -> FetchResult:
    if any(item.source == "aic" for item in items) and not (aic_contact and aic_contact.strip()):
        raise ValueError("AIC contact is required for image requests (email or project URL)")
    cache.mkdir(parents=True, exist_ok=True)
    result = FetchResult()
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for item in items:
            target = image_path(cache, item)
            if target.exists() and target.stat().st_size:
                result.skipped += 1
                continue
            tmp = target.with_suffix(target.suffix + ".part")
            tmp.unlink(missing_ok=True)
            headers = None
            if item.source == "aic":
                headers = {"AIC-User-Agent": f"weather-art-curation ({aic_contact.strip()})"}
            try:
                response = client.get(str(item.image.url), headers=headers)
                response.raise_for_status()
                tmp.write_bytes(response.content)
                tmp.replace(target)
                result.fetched += 1
            except (httpx.HTTPError, OSError) as exc:
                tmp.unlink(missing_ok=True)
                result.failures.append(ImageFailure(item.id, str(exc)))
            finally:
                if interval:
                    time.sleep(interval)
    return result
