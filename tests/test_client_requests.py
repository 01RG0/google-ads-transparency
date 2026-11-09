import json
from urllib.parse import parse_qs

import pytest

from client import TransparencyClient
from client.geo_targets import COUNTRY_GEO_TARGET_IDS, lookup_country_geo_target


class FakeResponse:
    status_code = 200
    headers = {}

    def json(self):
        return {"1": []}


class FakeHTTP:
    def __init__(self):
        self.url = None
        self.content = None

    async def post(self, url, content):
        self.url = url
        self.content = content
        return FakeResponse()

    async def aclose(self):
        pass


@pytest.mark.asyncio
async def test_search_advertisers_accepts_direct_suggestion_items():
    class SuggestionResponse(FakeResponse):
        def json(self):
            return {"1": [{"1": "Nike, Inc.", "2": "AR-example", "3": "US"}]}

    class SuggestionHTTP(FakeHTTP):
        async def post(self, url, content):
            self.url = url
            self.content = content
            return SuggestionResponse()

    client = TransparencyClient(client=SuggestionHTTP(), min_interval=0, max_retries=0)
    results = await client.search_advertisers("Nike", limit=2)

    assert results[0].name == "Nike, Inc."
    assert results[0].advertiser_id == "AR-example"
    assert results[0].country_code == "US"


@pytest.mark.asyncio
async def test_captured_region_and_custom_date_fields_are_encoded():
    transport = FakeHTTP()
    client = TransparencyClient(client=transport, min_interval=0, max_retries=0)
    await client.list_creatives(
        advertiser_id="AR-example",
        region="US",
        date_from="2026-11-01",
        date_to="2026-11-05",
    )
    form = parse_qs(transport.content)
    request = json.loads(form["f.req"][0])
    assert transport.url.endswith("SearchService/SearchCreatives?authuser=")
    assert request["3"]["6"] == 20261101
    assert request["3"]["7"] == 20261106
    assert request["3"]["8"] == [2840]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("region", "geo_id"),
    [
        ("GB", 2826),
        ("Egypt", 2818),
        ("Saudi Arabia", 2682),
        ("AE", 2784),
        ("Qatar", 2634),
        ("PS", 2275),
    ],
)
async def test_country_code_or_name_maps_to_geo_filter(region, geo_id):
    transport = FakeHTTP()
    client = TransparencyClient(client=transport, min_interval=0, max_retries=0)
    await client.list_creatives(region=region)
    request = json.loads(parse_qs(transport.content)["f.req"][0])
    assert request["3"]["8"] == [geo_id]


@pytest.mark.asyncio
async def test_duns_mapping_sends_empty_payload():
    class DunsFakeHTTP(FakeHTTP):
        async def post(self, url, content):
            self.url = url
            self.content = content
            return type("R", (), {
                "status_code": 200,
                "headers": {},
                "json": lambda self: {"1": [{"1": "AR123", "2": "456789"}]},
            })()

    transport = DunsFakeHTTP()
    client = TransparencyClient(client=transport, min_interval=0, max_retries=0)
    entries = await client.get_advertiser_duns_mapping()
    assert transport.url.endswith("TfaarAdvertiserService/GetAdvertiserDunsMapping?authuser=")
    payload = json.loads(parse_qs(transport.content)["f.req"][0])
    assert payload == {}
    assert entries[0].advertiser_id == "AR123"
    assert entries[0].duns_number == "456789"


def test_geo_target_dataset_has_global_country_coverage_and_anywhere_alias():
    assert len(COUNTRY_GEO_TARGET_IDS) >= 220
    assert lookup_country_geo_target("US") == lookup_country_geo_target("United States") == 2840
    assert lookup_country_geo_target("anywhere") is None
    assert lookup_country_geo_target("IR") is None
    assert lookup_country_geo_target("Palestine") == 2275
