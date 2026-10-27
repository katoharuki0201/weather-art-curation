import json

import httpx
import pytest

from curation.collect.common import RateClient


class FakeHttpClient:
    queue = []
    headers = None
    calls = 0

    def __init__(self, headers, **kwargs):
        type(self).headers = headers

    def get(self, url, params=None):
        type(self).calls += 1
        value = type(self).queue.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def close(self):
        pass


def response(status, payload=None, headers=None):
    request = httpx.Request("GET", "https://example.com")
    return httpx.Response(status, request=request, headers=headers, content=json.dumps(payload or {}).encode())


def setup_client(monkeypatch, queue, headers=None):
    FakeHttpClient.queue = list(queue)
    FakeHttpClient.calls = 0
    monkeypatch.setattr("curation.collect.common.httpx.Client", FakeHttpClient)
    return RateClient(0, headers=headers)


def test_default_headers_are_merged_with_caller_headers(monkeypatch):
    client = setup_client(monkeypatch, [response(200, {"ok": True})], {"AIC-User-Agent": "project (contact)"})
    assert client.get_json("https://example.com") == {"ok": True}
    assert FakeHttpClient.headers == {
        "User-Agent": "weather-art-curation/0.1",
        "Accept": "application/json",
        "AIC-User-Agent": "project (contact)",
    }


def test_retries_429_and_respects_retry_after(monkeypatch):
    sleeps = []
    monkeypatch.setattr("curation.collect.common.time.sleep", sleeps.append)
    client = setup_client(monkeypatch, [response(429, headers={"Retry-After": "2"}), response(200, {"ok": True})])
    assert client.get_json("https://example.com") == {"ok": True}
    assert FakeHttpClient.calls == 2
    assert sleeps == [2.0]


def test_retries_transport_error_and_5xx(monkeypatch):
    sleeps = []
    monkeypatch.setattr("curation.collect.common.time.sleep", sleeps.append)
    request = httpx.Request("GET", "https://example.com")
    client = setup_client(monkeypatch, [httpx.ConnectError("temporary", request=request), response(503), response(200, {"ok": True})])
    assert client.get_json("https://example.com") == {"ok": True}
    assert FakeHttpClient.calls == 3
    assert sleeps == [0.5, 1.0]


def test_does_not_retry_403(monkeypatch):
    client = setup_client(monkeypatch, [response(403)])
    with pytest.raises(httpx.HTTPStatusError):
        client.get_json("https://example.com")
    assert FakeHttpClient.calls == 1
