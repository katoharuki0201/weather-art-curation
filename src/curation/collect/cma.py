from ..models import Candidate, ImageRef
from .common import DEFAULT_QUERIES, CollectionResult, RateClient


def collect_cma(limit: int, include_works_on_paper: bool = False, existing_ids: set[str] | None = None, contact: str | None = None, queries: list[str] | None = None) -> CollectionResult:
    client = RateClient(0.1)
    search_terms = queries or DEFAULT_QUERIES["cma"]
    result = CollectionResult(queries=list(search_terms))
    existing_ids, seen = existing_ids or set(), set()
    try:
        for query in search_terms:
            skip = 0
            while len(result.items) < limit:
                batch_size = min(100, max(20, limit - len(result.items)))
                payload = client.get_json("https://openaccess-api.clevelandart.org/api/artworks/", {"q": query, "cc0": 1, "has_image": 1, "type": "Painting" if not include_works_on_paper else "", "limit": batch_size, "skip": skip})
                rows = payload.get("data", [])
                if not rows:
                    break
                for raw in rows:
                    result.scanned += 1
                    item_id = f"cma-{raw['id']}"
                    if item_id in seen:
                        result.duplicates += 1
                        continue
                    seen.add(item_id)
                    if item_id in existing_ids:
                        result.skipped_existing += 1
                        continue
                    web = (raw.get("images") or {}).get("web") or {}
                    if not web.get("url"):
                        result.rejected += 1
                        continue
                    creators = raw.get("creators") or []
                    result.items.append(Candidate(id=item_id, source="cma", title=raw.get("title") or "Untitled", artist=creators[0].get("description", "Unknown") if creators else "Unknown", date=raw.get("creation_date") or "", image=ImageRef(url=web["url"], thumbUrl=((raw.get("images") or {}).get("print") or {}).get("url") or web["url"]), sourceUrl=raw.get("url") or f"https://www.clevelandart.org/art/{raw['id']}", credit="Cleveland Museum of Art, CC0", subjects=[x.get("name", "") for x in raw.get("terms") or []]))
                    if len(result.items) >= limit:
                        break
                skip += len(rows)
                if len(rows) < batch_size:
                    break
            if len(result.items) >= limit:
                break
    finally:
        client.close()
    return result
