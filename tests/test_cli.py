from typer.testing import CliRunner

from curation import cli
from curation.images import FetchResult
from curation.io import append_jsonl
from curation.models import Candidate, ImageRef


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
