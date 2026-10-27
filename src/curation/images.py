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
    code: str = "request_failed"


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


def _is_aic_cloudflare_challenge(response: httpx.Response) -> bool:
    if response.status_code != 403:
        return False
    if response.headers.get("cf-mitigated", "").lower() == "challenge":
        return True
    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type:
        return False
    body = response.text[:10000].lower()
    return any(marker in body for marker in ("cloudflare", "cf-chl", "just a moment"))


def fetch_images(items: list[Candidate], cache: Path, interval: float = 1.0, aic_contact: str | None = None) -> FetchResult:
    if any(item.source == "aic" for item in items) and not (aic_contact and aic_contact.strip()):
        raise ValueError("AIC contact is required for image requests (email or project URL)")
    cache.mkdir(parents=True, exist_ok=True)
    result = FetchResult()
    aic_challenge_detected = False
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for item in items:
            target = image_path(cache, item)
            if target.exists() and target.stat().st_size:
                result.skipped += 1
                continue
            tmp = target.with_suffix(target.suffix + ".part")
            tmp.unlink(missing_ok=True)
            if item.source == "aic" and aic_challenge_detected:
                result.failures.append(ImageFailure(item.id, "AIC IIIF blocked by known Cloudflare challenge", "aic_cloudflare_challenge"))
                continue
            headers = None
            if item.source == "aic":
                headers = {"AIC-User-Agent": f"weather-art-curation ({aic_contact.strip()})"}
            try:
                response = client.get(str(item.image.url), headers=headers)
                if item.source == "aic" and _is_aic_cloudflare_challenge(response):
                    aic_challenge_detected = True
                    result.failures.append(ImageFailure(item.id, "AIC IIIF blocked by known Cloudflare challenge", "aic_cloudflare_challenge"))
                    continue
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
