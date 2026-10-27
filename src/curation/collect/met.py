import httpx
from pydantic import ValidationError

from ..models import Candidate, ImageRef
from .common import DEFAULT_QUERIES, CollectionResult, RateClient


def collect_met(limit: int, include_works_on_paper: bool = False, existing_ids: set[str] | None = None, contact: str | None = None, queries: list[str] | None = None) -> CollectionResult:
    client = RateClient(0.02)
    search_terms = queries or DEFAULT_QUERIES["met"]
    result = CollectionResult(queries=list(search_terms))
    existing_ids, seen = existing_ids or set(), set()
    try:
        for query in search_terms:
            offset = 0
            while len(result.items) < limit:
                payload = client.get_json("https://collectionapi.metmuseum.org/public/collection/v1.1/search", {"q": query, "hasImages": "true", "offset": offset, "limit": 100})
                ids = payload.get("objectIDs") or payload.get("objectIds") or []
                if not ids:
                    break
                for object_id in ids:
                    result.scanned += 1
                    item_id = f"met-{object_id}"
                    if item_id in seen:
                        result.duplicates += 1
                        continue
                    seen.add(item_id)
                    if item_id in existing_ids:
                        result.skipped_existing += 1
                        continue
                    try:
                        raw = client.get_json(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{object_id}")
                    except httpx.HTTPStatusError as exc:
                        status = exc.response.status_code
                        result.rejected += 1
                        result.record_detail_failure(f"http_{status}")
                        continue
                    except httpx.TransportError:
                        result.rejected += 1
                        result.record_detail_failure("network")
                        continue
                    try:
                        medium = (raw.get("medium") or "").lower()
                        allowed = "painting" in (raw.get("classification") or "").lower() or "oil" in medium or (include_works_on_paper and any(x in medium for x in ("print", "drawing", "paper")))
                        if not (raw.get("isPublicDomain") and raw.get("primaryImageSmall") and allowed):
                            result.rejected += 1
                            continue
                        result.items.append(Candidate(id=item_id, source="met", title=raw.get("title") or "Untitled", artist=raw.get("artistDisplayName") or "Unknown", date=raw.get("objectDate") or "", image=ImageRef(url=raw.get("primaryImage") or raw["primaryImageSmall"], thumbUrl=raw["primaryImageSmall"]), sourceUrl=raw.get("objectURL") or f"https://www.metmuseum.org/art/collection/search/{object_id}", credit=f"The Metropolitan Museum of Art, {raw.get('creditLine') or 'Public Domain'}", subjects=raw.get("tags") and [x.get("term", "") for x in raw["tags"]] or []))
                    except (ValidationError, KeyError, TypeError, ValueError):
                        result.rejected += 1
                        result.record_detail_failure("invalid_data")
                        continue
                    if len(result.items) >= limit:
                        break
                offset += len(ids)
                total = payload.get("total")
                if len(ids) < 100 or (isinstance(total, int) and offset >= total):
                    break
            if len(result.items) >= limit:
                break
    finally:
        client.close()
    return result
