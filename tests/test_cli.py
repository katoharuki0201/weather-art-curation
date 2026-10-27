from typer.testing import CliRunner

from curation import cli
from curation.images import FetchResult
from curation.io import append_jsonl, atomic_json
from curation.models import Candidate, Classified, ImageRef, Tags


def candidate(identifier, source):
    return Candidate(id=f"{source}-{identifier}", source=source, title="Sky", image=ImageRef(url=f"https://example.com/{identifier}.jpg"), sourceUrl=f"https://example.com/{identifier}", credit="Public Domain")


def test_fetch_images_source_filter_supports_repeat_and_commas(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    append_jsonl(tmp_path / "data/candidates.jsonl", [candidate(1, "aic"), candidate(2, "met"), candidate(3, "cma")])
    captured = []

    def fake_fetch(items, cache, interval, contact):
        captured.extend(item.source for item in items)
        return FetchResult(skipped=len(items))

    monkeypatch.setattr(cli, "fetch_all_images", fake_fetch)
    result = CliRunner().invoke(cli.app, ["fetch-images", "--source", "met,cma"])
    assert result.exit_code == 0
    assert captured == ["met", "cma"]
    assert "skipped=2" in result.stdout


def test_fetch_images_rejects_unknown_source(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli.app, ["fetch-images", "--source", "unknown"])
    assert result.exit_code != 0
    assert "unknown source" in result.output


def test_classify_source_filter_aggregates_missing_images(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    append_jsonl(tmp_path / "data/candidates.jsonl", [candidate(1, "aic"), candidate(2, "met")])
    result = CliRunner().invoke(cli.app, ["classify", "--source", "met"])
    assert result.exit_code == 0
    assert "missing_images=met=1" in result.stdout
    assert "aic=" not in result.stdout


def test_stats_uses_only_sky_visible_for_all_counts(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    visible = Classified(**candidate(1, "met").model_dump(), tags=Tags(weather=["clear"], time=["day"]), confidence=0.8, sky_visible=True)
    hidden = Classified(**candidate(2, "aic").model_dump(), tags=Tags(weather=["snow"], time=["night"]), confidence=0.9, sky_visible=False)
    append_jsonl(tmp_path / "data/classified.jsonl", [visible, hidden])
    atomic_json(tmp_path / "data/reviews.json", {
        visible.id: {"status": "approved", "tags": visible.tags.model_dump(), "updated_at": "2026-10-27T00:00:00Z"},
        hidden.id: {"status": "approved", "tags": hidden.tags.model_dump(), "updated_at": "2026-10-27T00:00:00Z"},
    })

    result = CliRunner().invoke(cli.app, ["stats"])

    assert result.exit_code == 0
    assert "progress: approved=1, rejected=0, skipped=0, unreviewed=0" in result.stdout
    assert "sources: aic=0, met=1, cma=0" in result.stdout
    assert "clear: day=1/60" in result.stdout
    assert "snow: day=0/30" in result.stdout
    assert "night=0/10" in result.stdout
