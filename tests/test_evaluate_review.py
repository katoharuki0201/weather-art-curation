from datetime import UTC, datetime

from fastapi.testclient import TestClient
from test_classify import FakeClassifier

from curation.classify.service import classify_one
from curation.evaluate import evaluate
from curation.io import append_jsonl
from curation.models import Tags
from curation.review import create_app


def test_evaluate(candidate, image_file):
    item = classify_one(candidate, image_file, FakeClassifier())
    report = evaluate([item], {item.id: Tags(weather=["clear"], time=["day"], season=["summer"])})
    assert report["weather"]["accuracy"] == 1


def test_review_api(candidate, image_file, tmp_path):
    classified = tmp_path / "classified.jsonl"
    reviews = tmp_path / "reviews.json"
    append_jsonl(classified, [classify_one(candidate, image_file, FakeClassifier())])
    client = TestClient(create_app(classified, reviews))
    assert client.get("/api/items").status_code == 200
    payload = {"status": "approved", "tags": {"weather": ["clear"], "time": ["day"], "season": []}, "updated_at": datetime.now(UTC).isoformat()}
    assert client.put("/api/reviews/aic-1", json=payload).status_code == 200
    assert client.get("/api/reviews").json()["aic-1"]["status"] == "approved"
    stats = client.get("/api/stats").json()
    assert stats["counts"]["clear"]["day"] == 1
    page = client.get("/").text
    assert "effectiveTags" in page
    assert "/api/stats" in page
    assert "weatherFilter" in page


def test_review_unknown_item_is_rejected(tmp_path):
    client = TestClient(create_app(tmp_path / "missing.jsonl", tmp_path / "reviews.json"))
    payload = {"status": "rejected", "tags": None, "updated_at": datetime.now(UTC).isoformat()}
    assert client.put("/api/reviews/unknown", json=payload).status_code == 404
