import re
import shutil
import subprocess
from datetime import UTC, datetime

import pytest
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
    assert "document.getElementById('weatherFilter')" in page
    assert "showError" in page
    assert "レビュー画面を初期化できませんでした" in page
    # ID-named elements must never rely on legacy window globals.
    for legacy_name in ("title", "status", "image", "tags", "scores", "weatherFilter", "timeFilter", "stats"):
        assert not re.search(rf"(?<![\w.]){legacy_name}\s*\.", page)
    assert client.get("/favicon.ico").status_code == 204


def test_review_unknown_item_is_rejected(tmp_path):
    client = TestClient(create_app(tmp_path / "missing.jsonl", tmp_path / "reviews.json"))
    payload = {"status": "rejected", "tags": None, "updated_at": datetime.now(UTC).isoformat()}
    assert client.put("/api/reviews/unknown", json=payload).status_code == 404


def test_generated_review_javascript_has_valid_syntax(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not installed; JavaScript syntax check cannot run")
    page = TestClient(create_app(tmp_path / "classified.jsonl", tmp_path / "reviews.json")).get("/").text
    match = re.search(r"<script>(.*?)</script>", page, re.DOTALL)
    assert match, "review page must contain an inline script"
    script_path = tmp_path / "review-page.js"
    script_path.write_text(match.group(1), encoding="utf-8")
    checked = subprocess.run([node, "--check", str(script_path)], capture_output=True, text=True, check=False)
    assert checked.returncode == 0, checked.stderr
