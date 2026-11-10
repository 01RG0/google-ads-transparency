"""Synchronous wrapper around TransparencyClient for use in non-async code."""
from __future__ import annotations

import asyncio
from typing import Iterator

from .client import TransparencyClient
from .models import (
    Advertiser,
    AdvertiserSuggestion,
    Creative,
    CreativeDetail,
    CreativePage,
    DunsMappingEntry,
)


class SyncTransparencyClient:
    def __init__(self, *, timeout: float = 20, min_interval: float = 0.25, max_retries: int = 3) -> None:
        self._client = TransparencyClient(timeout=timeout, min_interval=min_interval, max_retries=max_retries)

    def __enter__(self) -> "SyncTransparencyClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        asyncio.run(self._client.close())

    def search_advertisers(self, query: str, *, limit: int = 10) -> list[AdvertiserSuggestion]:
        return asyncio.run(self._client.search_advertisers(query, limit=limit))

    def get_advertiser(self, advertiser_id: str) -> Advertiser | None:
        return asyncio.run(self._client.get_advertiser(advertiser_id))

    def list_creatives(self, advertiser_id: str | None = None, region: str | None = None,
                       date_from: str | None = None, date_to: str | None = None,
                       cursor: str | None = None, *, domain: str | None = None,
                       page_size: int = 40) -> CreativePage:
        return asyncio.run(self._client.list_creatives(
            advertiser_id=advertiser_id, region=region,
            date_from=date_from, date_to=date_to,
            cursor=cursor, domain=domain, page_size=page_size,
        ))

    def search_by_domain(self, domain: str, *, cursor: str | None = None, page_size: int = 40) -> CreativePage:
        return asyncio.run(self._client.search_by_domain(domain, cursor=cursor, page_size=page_size))

    def get_creative(self, advertiser_id: str, creative_id: str) -> CreativeDetail | None:
        return asyncio.run(self._client.get_creative(advertiser_id, creative_id))

    def get_advertiser_duns_mapping(self) -> list[DunsMappingEntry]:
        return asyncio.run(self._client.get_advertiser_duns_mapping())

    def paginate(self, advertiser_id: str | None = None, region: str | None = None,
                 date_from: str | None = None, date_to: str | None = None,
                 *, domain: str | None = None, page_size: int = 40) -> Iterator[Creative]:
        cursor: str | None = None
        while True:
            page = self.list_creatives(
                advertiser_id=advertiser_id, region=region,
                date_from=date_from, date_to=date_to,
                cursor=cursor, domain=domain, page_size=page_size,
            )
            yield from page.creatives
            if page.next_cursor is None:
                return
            cursor = page.next_cursor
