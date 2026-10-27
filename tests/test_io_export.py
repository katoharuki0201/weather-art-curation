import json
from datetime import UTC, datetime

from test_classify import FakeClassifier

from curation.classify.service import classify_one
from curation.export import export_artworks
from curation.io import atomic_json, read_json
from curation.models import Tags


def test_atomic_json(tmp_path):
    path = tmp_path / "nested/value.json"
    atomic_json(path, {"hello": "世界"})
    assert read_json(path) == {"hello": "世界"}


def test_export(candidate, image_file, tmp_path):
    item = classify_one(candidate, image_file, FakeClassifier())
    reviews = tmp_path / "reviews.json"
    atomic_json(reviews, {item.id: {"status": "approved", "tags": Tags(weather=["snow"], time=["night"]).model_dump(), "updated_at": datetime.now(UTC).isoformat()}})
    schema = tmp_path / "schema.json"
    schema.write_text((__import__("pathlib").Path("schema/artwork.schema.json")).read_text(), encoding="utf-8")
    output = tmp_path / "artworks.json"
    result = export_artworks([item], reviews, schema, output)
    assert result[0]["tags"]["weather"] == ["snow"]
    assert json.loads(output.read_text())[0]["id"] == "aic-1"

