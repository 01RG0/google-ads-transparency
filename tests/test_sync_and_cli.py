"""Smoke tests for SyncTransparencyClient and the python -m client CLI."""
import json
from urllib.parse import parse_qs

import pytest

from client import SyncTransparencyClient
from client.sync_client import SyncTransparencyClient as _SyncDirect


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


def test_sync_client_exported_from_package():
    assert SyncTransparencyClient is _SyncDirect


def test_sync_search_advertisers_returns_list():
    transport = FakeHTTP()

    class SuggestResponse(FakeResponse):
        def json(self):
            return {"1": [{"1": {"1": "Nike, Inc.", "2": "AR-example", "3": "US"}}]}

    transport_real = FakeHTTP()
    transport_real.post_orig = transport_real.post

    import asyncio

    async def fake_post(url, content):
        transport_real.url = url
        transport_real.content = content
        return SuggestResponse()

    transport_real.post = fake_post

    from client.client import TransparencyClient
    inner = TransparencyClient(client=transport_real, min_interval=0, max_retries=0)
    client = SyncTransparencyClient.__new__(SyncTransparencyClient)
    client._client = inner

    results = client.search_advertisers("Nike")
    assert isinstance(results, list)
    assert transport_real.url.endswith("SearchService/SearchSuggestions?authuser=")


def test_sync_list_creatives_returns_page():
    transport = FakeHTTP()

    class CreativesResponse(FakeResponse):
        def json(self):
            return {"1": []}

    async def fake_post(url, content):
        transport.url = url
        transport.content = content
        return CreativesResponse()

    transport.post = fake_post

    from client.client import TransparencyClient
    inner = TransparencyClient(client=transport, min_interval=0, max_retries=0)
    client = SyncTransparencyClient.__new__(SyncTransparencyClient)
    client._client = inner

    page = client.list_creatives(region="US")
    assert page.creatives == []
    assert transport.url.endswith("SearchService/SearchCreatives?authuser=")


def test_sync_paginate_stops_when_no_cursor():
    transport = FakeHTTP()

    class OnePage(FakeResponse):
        def json(self):
            return {"1": [{"1": "AR1", "2": "CR1"}]}

    async def fake_post(url, content):
        transport.url = url
        transport.content = content
        return OnePage()

    transport.post = fake_post

    from client.client import TransparencyClient
    inner = TransparencyClient(client=transport, min_interval=0, max_retries=0)
    client = SyncTransparencyClient.__new__(SyncTransparencyClient)
    client._client = inner

    creatives = list(client.paginate())
    assert len(creatives) == 1
    assert creatives[0].creative_id == "CR1"


def test_cli_help_exits_zero():
    from client.__main__ import build_parser
    parser = build_parser()
    import argparse
    try:
        parser.parse_args(["--help"])
    except SystemExit as exc:
        assert exc.code == 0


def test_cli_search_advertisers_subcommand_parses():
    from client.__main__ import build_parser
    parser = build_parser()
    args = parser.parse_args(["search-advertisers", "Nike", "--limit", "5"])
    assert args.command == "search-advertisers"
    assert args.query == "Nike"
    assert args.limit == 5


def test_cli_list_creatives_subcommand_parses():
    from client.__main__ import build_parser
    parser = build_parser()
    args = parser.parse_args([
        "list-creatives",
        "--advertiser", "AR123",
        "--region", "US",
        "--from", "2026-01-01",
        "--to", "2026-12-31",
        "--pages", "3",
    ])
    assert args.command == "list-creatives"
    assert args.advertiser == "AR123"
    assert args.region == "US"
    assert args.date_from == "2026-01-01"
    assert args.date_to == "2026-12-31"
    assert args.pages == 3


def test_cli_get_advertiser_subcommand_parses():
    from client.__main__ import build_parser
    parser = build_parser()
    args = parser.parse_args(["get-advertiser", "AR999"])
    assert args.command == "get-advertiser"
    assert args.advertiser_id == "AR999"
