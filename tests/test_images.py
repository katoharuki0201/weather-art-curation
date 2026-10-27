import httpx
import pytest

from curation.images import fetch_images, image_path
from curation.models import Candidate, ImageRef


def make_candidate(identifier, source="aic"):
    return Candidate(id=f"{source}-{identifier}", source=source, title="Sky", image=ImageRef(url=f"https://example.com/{identifier}.jpg"), sourceUrl=f"https://example.com/work/{identifier}", credit="Public Domain")


class FakeResponse:
    def __init__(self, content=b"image", error=None):
        self.content = content
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error


class FakeHttpClient:
    responses = []
    calls = []

    def __init__(self, **kwargs):
        self.queue = list(self.responses)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get(self, url, headers=None):
        self.calls.append((url, headers))
        return self.queue.pop(0)


def test_aic_contact_required_before_http(monkeypatch, tmp_path):
    def unexpected_client(**kwargs):
        raise AssertionError("HTTP client must not be created")

    monkeypatch.setattr("curation.images.httpx.Client", unexpected_client)
    with pytest.raises(ValueError, match="AIC contact"):
        fetch_images([make_candidate(1)], tmp_path, interval=0)


def test_partial_success_headers_cleanup_and_cache_skip(monkeypatch, tmp_path):
    first = make_candidate(1)
    failed = make_candidate(2)
    cached = make_candidate(3, "met")
    cached_path = image_path(tmp_path, cached)
    tmp_path.mkdir(exist_ok=True)
    cached_path.write_bytes(b"cached")
    failed_part = image_path(tmp_path, failed).with_suffix(".jpg.part")
    failed_part.write_bytes(b"stale")
    request = httpx.Request("GET", str(failed.image.url))
    response = httpx.Response(403, request=request)
    error = httpx.HTTPStatusError("403 Forbidden", request=request, response=response)
    FakeHttpClient.responses = [FakeResponse(b"good"), FakeResponse(error=error)]
    FakeHttpClient.calls = []
    monkeypatch.setattr("curation.images.httpx.Client", FakeHttpClient)

    result = fetch_images([first, failed, cached], tmp_path, interval=0, aic_contact="owner@example.com")

    assert (result.fetched, result.skipped, result.failed) == (1, 1, 1)
    assert result.failures[0].id == "aic-2"
    assert image_path(tmp_path, first).read_bytes() == b"good"
    assert not failed_part.exists()
    assert FakeHttpClient.calls[0][1] == {"AIC-User-Agent": "weather-art-curation (owner@example.com)"}
    assert FakeHttpClient.calls[1][1] == {"AIC-User-Agent": "weather-art-curation (owner@example.com)"}
    assert len(FakeHttpClient.calls) == 2
