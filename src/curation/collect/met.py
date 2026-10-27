from ..models import Candidate, ImageRef
from .common import CollectionResult, RateClient


def collect_met(limit: int, include_works_on_paper: bool = False, existing_ids: set[str] | None = None, contact: str | None = None) -> CollectionResult:
    client = RateClient(0.02)
    result = CollectionResult()
    existing_ids = existing_ids or set()
    try:
        ids = client.get_json("https://collectionapi.metmuseum.org/public/collection/v1/search", {"q": "landscape sky", "hasImages": "true"}).get("objectIDs") or []
        for object_id in ids:
            if len(result.items) >= limit:
                break
            item_id = f"met-{object_id}"
            if item_id in existing_ids:
                result.skipped_existing += 1
                continue
            raw = client.get_json(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{object_id}")
            medium = (raw.get("medium") or "").lower()
            allowed = "painting" in (raw.get("classification") or "").lower() or "oil" in medium or (include_works_on_paper and any(x in medium for x in ("print", "drawing", "paper")))
            if not (raw.get("isPublicDomain") and raw.get("primaryImageSmall") and allowed):
                result.rejected += 1
                continue
            result.items.append(Candidate(id=item_id, source="met", title=raw.get("title") or "Untitled", artist=raw.get("artistDisplayName") or "Unknown", date=raw.get("objectDate") or "", image=ImageRef(url=raw.get("primaryImage") or raw["primaryImageSmall"], thumbUrl=raw["primaryImageSmall"]), sourceUrl=raw.get("objectURL") or f"https://www.metmuseum.org/art/collection/search/{object_id}", credit=f"The Metropolitan Museum of Art, {raw.get('creditLine') or 'Public Domain'}", subjects=raw.get("tags") and [x.get("term", "") for x in raw["tags"]] or []))
    finally:
        client.close()
    return result
