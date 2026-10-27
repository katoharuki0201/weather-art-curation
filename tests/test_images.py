import httpx
import pytest

from curation.images import fetch_images, image_path
from curation.models import Candidate, ImageRef


def make_candidate(identifier, source="aic"):
    return Candidate(id=f"{source}-{identifier}", source=source, title="Sky", image=ImageRef(url=f"https://example.com/{identifier}.jpg"), sourceUrl=f"https://example.com/work/{identifier}", credit="Public Domain")


class FakeResponse:
    def __init__(self, content=b"image", error=None, status_code=200, headers=None, text=""):
        self.content = content
        self.error = error
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text

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


@pytest.mark.parametrize(
    ("headers", "text"),
    [
        ({"cf-mitigated": "challenge"}, ""),
        ({"content-type": "text/html"}, "<title>Just a moment...</title><p>Cloudflare</p>"),
    ],
)
def test_aic_cloudflare_challenge_stops_later_aic_requests(monkeypatch, tmp_path, headers, text):
    items = [make_candidate(1), make_candidate(2), make_candidate(3, "met")]
    FakeHttpClient.responses = [FakeResponse(status_code=403, headers=headers, text=text), FakeResponse(b"met-image")]
    FakeHttpClient.calls = []
    monkeypatch.setattr("curation.images.httpx.Client", FakeHttpClient)

    result = fetch_images(items, tmp_path, interval=0, aic_contact="owner@example.com")

    assert result.fetched == 1
    assert [failure.id for failure in result.failures] == ["aic-1", "aic-2"]
    assert {failure.code for failure in result.failures} == {"aic_cloudflare_challenge"}
    assert len(FakeHttpClient.calls) == 2


def test_normal_403_is_not_cloudflare_challenge(monkeypatch, tmp_path):
    item = make_candidate(1)
    request = httpx.Request("GET", str(item.image.url))
    response = httpx.Response(403, request=request)
    error = httpx.HTTPStatusError("403 Forbidden", request=request, response=response)
    FakeHttpClient.responses = [FakeResponse(error=error, status_code=403)]
    FakeHttpClient.calls = []
    monkeypatch.setattr("curation.images.httpx.Client", FakeHttpClient)
    result = fetch_images([item], tmp_path, interval=0, aic_contact="owner@example.com")
    assert result.failures[0].code == "request_failed"
