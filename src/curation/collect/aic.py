from ..models import Candidate, ImageRef
from .common import CollectionResult, RateClient


def collect_aic(limit: int, include_works_on_paper: bool = False, existing_ids: set[str] | None = None, contact: str | None = None) -> CollectionResult:
    if not contact or not contact.strip():
        raise ValueError("AIC contact is required (email or project URL)")
    client = RateClient(1.0, {"AIC-User-Agent": f"weather-art-curation ({contact.strip()})"})
    fields = "id,title,artist_display,date_display,image_id,is_public_domain,artwork_type_title,subject_titles"
    result, page = CollectionResult(), 1
    existing_ids = existing_ids or set()
    try:
        while len(result.items) < limit:
            payload = client.get_json("https://api.artic.edu/api/v1/artworks/search", {"q": "landscape seascape cityscape sky", "page": page, "limit": min(100, max(20, limit)), "fields": fields})
            for raw in payload.get("data", []):
                kind = (raw.get("artwork_type_title") or "").lower()
                allowed = "painting" in kind or (include_works_on_paper and any(x in kind for x in ("print", "drawing")))
                if not (raw.get("is_public_domain") and raw.get("image_id") and allowed):
                    result.rejected += 1
                    continue
                item_id = f"aic-{raw['id']}"
                if item_id in existing_ids:
                    result.skipped_existing += 1
                    continue
                image_id = raw["image_id"]
                artist = (raw.get("artist_display") or "Unknown").split("\n", 1)[0]
                result.items.append(Candidate(id=item_id, source="aic", title=raw.get("title") or "Untitled", artist=artist, date=raw.get("date_display") or "", image=ImageRef(url=f"https://www.artic.edu/iiif/2/{image_id}/full/843,/0/default.jpg", thumbUrl=f"https://www.artic.edu/iiif/2/{image_id}/full/200,/0/default.jpg"), sourceUrl=f"https://www.artic.edu/artworks/{raw['id']}", credit="Art Institute of Chicago, Public Domain", subjects=raw.get("subject_titles") or []))
                if len(result.items) >= limit:
                    break
            if not payload.get("pagination", {}).get("next_url"):
                break
            page += 1
    finally:
        client.close()
    return result
