from pathlib import Path

import jsonschema

from .io import atomic_json, read_json
from .models import Classified, Review


def export_artworks(items: list[Classified], reviews_path: Path, schema_path: Path, output: Path) -> list[dict]:
    reviews = {key: Review.model_validate(value) for key, value in read_json(reviews_path, {}).items()}
    artworks = []
    for item in items:
        review = reviews.get(item.id)
        if not review or review.status != "approved":
            continue
        data = item.model_dump(by_alias=True, mode="json", exclude={"scores", "confidence", "sky_visible", "color_features", "subjects", "public_domain"})
        data["tags"] = (review.tags or item.tags).model_dump(mode="json")
        artworks.append(data)
    schema = read_json(schema_path)
    jsonschema.validate(artworks, schema)
    atomic_json(output, artworks)
    return artworks

