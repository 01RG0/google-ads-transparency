"""Contract checks against sanitized response examples captured from the site."""
import json
from pathlib import Path

import pytest

from client.errors import ResponseShapeError
from client.models import CreativeDetail, CreativePage, DunsMappingEntry

SAMPLES = Path(__file__).parents[1] / "docs" / "samples"


def read_sample(name: str):
    path = SAMPLES / name
    assert path.is_file(), f"required response sample missing: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_search_creatives_sample_matches_contract():
    payload = read_sample("POST__anji___rpc_searchservice_searchcreatives.json")
    try:
        page = CreativePage.model_validate(payload)
    except Exception as exc:
        raise ResponseShapeError("Saved SearchCreatives sample no longer matches the model") from exc
    assert page.creatives, "captured SearchCreatives page unexpectedly has no creatives"
    assert page.next_cursor, "captured first page should include a pagination cursor"
    assert page.creatives[0].creative_id
    assert page.creatives[0].advertiser_id


def test_advertiser_not_found_sample_is_empty_object():
    assert read_sample("POST__anji___rpc_lookupservice_getadvertiserbyid.json") == {}


def test_advertiser_found_sample_matches_observed_shape():
    payload = read_sample("POST__anji___rpc_lookupservice_getadvertiserbyid_found.json")
    assert isinstance(payload.get("1"), dict)
    advertiser = payload["1"]
    assert advertiser.get("1", "").startswith("AR")
    assert advertiser.get("2")


def test_creative_detail_sample_matches_contract():
    payload = read_sample("POST__anji___rpc_lookupservice_getcreativebyid.json")
    assert isinstance(payload.get("1"), dict)
    try:
        detail = CreativeDetail.model_validate(payload["1"])
    except Exception as exc:
        raise ResponseShapeError("Saved GetCreativeById sample no longer matches the model") from exc
    assert detail.creative_id
    assert detail.variations


def test_duns_mapping_sample_matches_contract():
    payload = read_sample("POST__anji___rpc_tfaaradvertiserservice_getadvertiserdunsmapping.json")
    rows = payload.get("1")
    assert isinstance(rows, list) and rows, "DUNS mapping sample must be a non-empty list"
    try:
        entries = [DunsMappingEntry.model_validate(r) for r in rows]
    except Exception as exc:
        raise ResponseShapeError("Saved GetAdvertiserDunsMapping sample no longer matches the model") from exc
    assert entries[0].advertiser_id.startswith("AR")
    assert entries[0].duns_number.isdigit()
