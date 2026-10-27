import httpx
import pytest

from curation.collect import aic, cma, met


class FakeClient:
    responses = []
    instances = []

    def __init__(self, interval, headers=None):
        self.headers = headers or {}
        self.calls = []
        self.queue = list(self.responses)
        self.instances.append(self)

    def get_json(self, url, params=None):
        self.calls.append((url, params))
        value = self.queue.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def close(self):
        pass


def aic_row(identifier):
    return {"id": identifier, "title": f"Work {identifier}", "artist_display": "Artist", "date_display": "1900", "image_id": f"image-{identifier}", "is_public_domain": True, "artwork_type_title": "Painting", "subject_titles": ["Landscape"]}


def met_row(identifier):
    return {"objectID": identifier, "title": f"Work {identifier}", "artistDisplayName": "Artist", "objectDate": "1900", "primaryImageSmall": f"https://example.com/{identifier}.jpg", "primaryImage": "", "objectURL": f"https://example.com/work/{identifier}", "isPublicDomain": True, "classification": "Paintings", "medium": "Oil", "tags": []}


def cma_row(identifier):
    return {"id": identifier, "title": f"Work {identifier}", "creation_date": "1900", "images": {"web": {"url": f"https://example.com/{identifier}.jpg"}}, "creators": [], "terms": []}


def test_aic_requires_contact_and_paginates_past_existing(monkeypatch):
    with pytest.raises(ValueError):
        aic.collect_aic(1)
    FakeClient.responses = [
        {"data": [aic_row(1)], "pagination": {"next_url": "page2"}},
        {"data": [aic_row(2)], "pagination": {"next_url": None}},
    ]
    FakeClient.instances = []
    monkeypatch.setattr(aic, "RateClient", FakeClient)
    result = aic.collect_aic(1, existing_ids={"aic-1"}, contact="owner@example.com")
    assert [item.id for item in result.items] == ["aic-2"]
    assert result.skipped_existing == 1
    assert FakeClient.instances[0].headers["AIC-User-Agent"] == "weather-art-curation (owner@example.com)"


def test_met_skips_existing_without_detail_request(monkeypatch):
    FakeClient.responses = [{"objectIDs": [1, 2]}, met_row(2)]
    FakeClient.instances = []
    monkeypatch.setattr(met, "RateClient", FakeClient)
    result = met.collect_met(1, existing_ids={"met-1"})
    assert [item.id for item in result.items] == ["met-2"]
    assert result.skipped_existing == 1
    assert len(FakeClient.instances[0].calls) == 2
    assert "/v1.1/search" in FakeClient.instances[0].calls[0][0]
    assert FakeClient.instances[0].calls[0][1]["offset"] == 0
    assert result.scanned == 2


def test_met_isolates_missing_and_invalid_detail_records(monkeypatch):
    request = httpx.Request("GET", "https://collectionapi.metmuseum.org/public/collection/v1/objects/1")
    missing = httpx.Response(404, request=request)
    missing_error = httpx.HTTPStatusError("not found", request=request, response=missing)
    invalid = met_row(2)
    invalid["primaryImageSmall"] = "not-a-url"
    FakeClient.responses = [{"objectIDs": [1, 2, 3]}, missing_error, invalid, met_row(3)]
    FakeClient.instances = []
    monkeypatch.setattr(met, "RateClient", FakeClient)

    result = met.collect_met(1, queries=["landscape"])

    assert [item.id for item in result.items] == ["met-3"]
    assert result.scanned == 3
    assert result.rejected == 2
    assert result.failed_detail == 2
    assert result.detail_failures == {"http_404": 1, "invalid_data": 1}


def test_met_searches_in_500_id_pages_with_delay(monkeypatch):
    first_page = list(range(1, 501))
    FakeClient.responses = [
        {"total": 501, "objectIDs": first_page},
        {"total": 501, "objectIDs": [501]},
        met_row(501),
    ]
    FakeClient.instances = []
    sleeps = []
    monkeypatch.setattr(met, "RateClient", FakeClient)
    monkeypatch.setattr(met.time, "sleep", sleeps.append)

    result = met.collect_met(1, existing_ids={f"met-{identifier}" for identifier in first_page}, queries=["landscape"])

    assert [item.id for item in result.items] == ["met-501"]
    calls = FakeClient.instances[0].calls
    assert calls[0][1]["limit"] == 500
    assert calls[0][1]["offset"] == 0
    assert calls[1][1]["limit"] == 500
    assert calls[1][1]["offset"] == 500
    assert sleeps == [1.0]


def test_cma_paginates_until_new_limit(monkeypatch):
    first = [cma_row(i) for i in range(1, 21)]
    second = [cma_row(i) for i in range(21, 41)]
    FakeClient.responses = [{"data": first}, {"data": second}]
    FakeClient.instances = []
    monkeypatch.setattr(cma, "RateClient", FakeClient)
    result = cma.collect_cma(2, existing_ids={f"cma-{i}" for i in range(1, 21)})
    assert [item.id for item in result.items] == ["cma-21", "cma-22"]
    assert result.skipped_existing == 20
    assert FakeClient.instances[0].calls[1][1]["skip"] == 20


def test_cma_deduplicates_across_queries(monkeypatch):
    FakeClient.responses = [{"data": [cma_row(1)]}, {"data": [cma_row(1), cma_row(2)]}]
    FakeClient.instances = []
    monkeypatch.setattr(cma, "RateClient", FakeClient)
    result = cma.collect_cma(2, queries=["landscape", "sky"])
    assert [item.id for item in result.items] == ["cma-1", "cma-2"]
    assert result.duplicates == 1
    assert result.queries == ["landscape", "sky"]
