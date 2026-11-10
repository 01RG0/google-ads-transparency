"""Opt-in network smoke test: run with pytest -m live."""
import os

import pytest

from client import TransparencyClient

pytestmark = pytest.mark.live


@pytest.mark.asyncio
async def test_live_advertiser_search():
    if os.getenv("ADS_TRANSPARENCY_LIVE") != "1":
        pytest.skip("set ADS_TRANSPARENCY_LIVE=1 to enable the live smoke test")
    async with TransparencyClient() as client:
        results = await client.search_advertisers("Nike", limit=2)
        assert isinstance(results, list) and results
        advertiser_id = results[0].advertiser_id
        assert advertiser_id and advertiser_id.startswith("AR")
        page = await client.list_creatives(advertiser_id=advertiser_id, region="US")
    assert page.creatives is not None


@pytest.mark.asyncio
async def test_live_search_by_domain():
    if os.getenv("ADS_TRANSPARENCY_LIVE") != "1":
        pytest.skip("set ADS_TRANSPARENCY_LIVE=1 to enable the live smoke test")
    async with TransparencyClient() as client:
        page = await client.search_by_domain("nike.com", page_size=5)
    assert isinstance(page.creatives, list)
    assert len(page.creatives) <= 5


@pytest.mark.asyncio
async def test_live_get_creative():
    if os.getenv("ADS_TRANSPARENCY_LIVE") != "1":
        pytest.skip("set ADS_TRANSPARENCY_LIVE=1 to enable the live smoke test")
    async with TransparencyClient() as client:
        results = await client.search_advertisers("Nike", limit=2)
        assert results
        advertiser_id = results[0].advertiser_id
        page = await client.list_creatives(advertiser_id=advertiser_id, region="US")
        assert page.creatives
        creative = page.creatives[0]
        detail = await client.get_creative(creative.advertiser_id, creative.creative_id)
    assert detail is not None
    assert detail.creative_id == creative.creative_id


@pytest.mark.asyncio
async def test_live_duns_mapping_returns_large_dataset():
    if os.getenv("ADS_TRANSPARENCY_LIVE") != "1":
        pytest.skip("set ADS_TRANSPARENCY_LIVE=1 to enable the live smoke test")
    async with TransparencyClient() as client:
        entries = await client.get_advertiser_duns_mapping()
    assert len(entries) > 100
    assert entries[0].advertiser_id.startswith("AR")
    assert entries[0].duns_number.isdigit()
