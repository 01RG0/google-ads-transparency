"""Async httpx client for the public Google Ads Transparency Center RPCs."""
from __future__ import annotations

import asyncio
import json
import random
import time
from collections.abc import AsyncGenerator
from datetime import date, timedelta
from typing import Any
from urllib.parse import quote_plus

import httpx
from pydantic import ValidationError

from .errors import ResponseShapeError, UnsupportedFilterError, UpstreamHTTPError
from .geo_targets import lookup_country_geo_target
from .models import Advertiser, AdvertiserSuggestion, Creative, CreativeDetail, CreativePage, DunsMappingEntry


class TransparencyClient:
    BASE_URL = "https://adstransparency.google.com/anji/_/rpc/"
    RETRY_STATUSES = {429, 500, 502, 503, 504}

    def __init__(self, *, timeout: float = 20, min_interval: float = 0.25,
                 max_retries: int = 3, client: httpx.AsyncClient | None = None,
                 proxy: str | None = None, proxies: list[str] | None = None,
                 verbose: bool = False) -> None:
        self._timeout_val = timeout
        self._base_headers = {
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://adstransparency.google.com",
            "referer": "https://adstransparency.google.com/",
            "x-same-domain": "1",
        }
        self._proxies: list[str] | None = None

        if proxies:
            self._proxies = list(proxies)
            self._http = client or httpx.AsyncClient(timeout=timeout, headers=self._base_headers)
            self._owns_client = client is None
        elif proxy:
            self._http = client or httpx.AsyncClient(timeout=timeout, proxy=proxy, headers=self._base_headers)
            self._owns_client = client is None
        else:
            self._http = client or httpx.AsyncClient(timeout=timeout, headers=self._base_headers)
            self._owns_client = client is None

        self.min_interval = max(0.0, min_interval)
        self.max_retries = max(0, max_retries)
        self.verbose = verbose
        self._rate_lock = asyncio.Lock()
        self._last_request = 0.0

    async def __aenter__(self) -> "TransparencyClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def _throttle(self) -> None:
        async with self._rate_lock:
            delay = self.min_interval - (time.monotonic() - self._last_request)
            if delay > 0:
                if self.verbose:
                    print(f"[verbose] rate-limiting: sleeping {delay:.2f}s", flush=True)
                await asyncio.sleep(delay)
            self._last_request = time.monotonic()

    async def _rpc(self, service_method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = self.BASE_URL + service_method + "?authuser="
        body = "f.req=" + quote_plus(json.dumps(payload, separators=(",", ":")))

        if self._proxies:
            proxy = random.choice(self._proxies)
            async with httpx.AsyncClient(timeout=self._timeout_val, proxy=proxy, headers=self._base_headers) as http:
                return await self._rpc_with_client(http, url, body)
        else:
            return await self._rpc_with_client(self._http, url, body)

    async def _rpc_with_client(self, http: httpx.AsyncClient, url: str, body: str) -> dict[str, Any]:
        for attempt in range(self.max_retries + 1):
            await self._throttle()
            try:
                response = await http.post(url, content=body)
            except httpx.TransportError as exc:
                if attempt >= self.max_retries:
                    raise UpstreamHTTPError(f"RPC transport failed: {exc.__class__.__name__}") from exc
                sleep = min(8.0, 0.5 * 2**attempt) + random.uniform(0, 0.25)
                if self.verbose:
                    print(f"[verbose] transport error ({exc.__class__.__name__}), retry {attempt+1}/{self.max_retries}, sleeping {sleep:.1f}s", flush=True)
                await asyncio.sleep(sleep)
                continue
            if response.status_code in self.RETRY_STATUSES and attempt < self.max_retries:
                retry_after = response.headers.get("retry-after")
                try:
                    delay = float(retry_after) if retry_after else 0.5 * 2**attempt
                except ValueError:
                    delay = 0.5 * 2**attempt
                sleep = min(15.0, delay) + random.uniform(0, 0.25)
                if self.verbose:
                    print(f"[verbose] HTTP {response.status_code}, retry {attempt+1}/{self.max_retries}, sleeping {sleep:.1f}s", flush=True)
                await asyncio.sleep(sleep)
                continue
            if response.status_code >= 400:
                raise UpstreamHTTPError(f"RPC returned HTTP {response.status_code}")
            try:
                value = response.json()
            except ValueError as exc:
                raise ResponseShapeError("RPC response was not valid JSON") from exc
            if not isinstance(value, dict):
                raise ResponseShapeError("RPC response must be a JSON object")
            return value
        raise AssertionError("unreachable")

    @staticmethod
    def _model(model: type, value: Any, endpoint: str):
        try:
            return model.model_validate(value)
        except (ValidationError, TypeError) as exc:
            keys = list(value.keys()) if isinstance(value, dict) else type(value).__name__
            raise ResponseShapeError(f"Unexpected response shape from {endpoint}: got keys {keys}") from exc

    async def search_advertisers(self, query: str, *, limit: int = 10) -> list[AdvertiserSuggestion]:
        data = await self._rpc("SearchService/SearchSuggestions", {"1": query, "2": limit, "3": limit, "5": {"1": 1}})
        rows = data.get("1")
        if not isinstance(rows, list):
            raise ResponseShapeError(f"SearchSuggestions response missing list field '1'; got keys {list(data.keys())}")
        results = []
        for row in rows:
            if not isinstance(row, dict):
                raise ResponseShapeError(f"SearchSuggestions item missing object field '1'; got {type(row).__name__}")
            if isinstance(row.get("1"), dict):
                inner = row["1"]
            elif isinstance(row.get("2"), str):
                inner = row
            else:
                raise ResponseShapeError(f"SearchSuggestions item missing object field '1'; got keys {list(row.keys())}")
            results.append(AdvertiserSuggestion.model_validate({**inner, "raw": inner}))
        return results

    async def get_advertiser(self, advertiser_id: str) -> Advertiser | None:
        data = await self._rpc("LookupService/GetAdvertiserById", {"1": advertiser_id, "3": {"1": 1}})
        if not data:
            return None
        if not isinstance(data.get("1"), dict):
            raise ResponseShapeError(f"GetAdvertiserById response missing object field '1'; got keys {list(data.keys())}")
        return self._model(Advertiser, data["1"], "GetAdvertiserById")

    async def list_creatives(self, advertiser_id: str | None = None, region: str | None = None,
                             date_from: str | None = None, date_to: str | None = None,
                             cursor: str | None = None, *, domain: str | None = None,
                             page_size: int = 40) -> CreativePage:
        if (date_from is None) != (date_to is None):
            raise ValueError("date_from and date_to must be supplied together")
        if not 1 <= page_size <= 40:
            raise ValueError("page_size must be between 1 and 40")
        filters: dict[str, Any] = {}
        if domain is not None:
            filters["12"] = {"1": domain, "2": True}
        if advertiser_id is not None:
            filters["13"] = {"1": [advertiser_id]}
        if region is not None:
            geo_target_id = lookup_country_geo_target(region)
            if geo_target_id is None and region.strip().casefold() not in {"", "anywhere", "all", "worldwide"}:
                raise UnsupportedFilterError(
                    f"Unknown or inactive country/territory {region!r}; use an active ISO alpha-2 code or official country name."
                )
            if geo_target_id is not None:
                filters["8"] = [geo_target_id]
        if date_from is not None and date_to is not None:
            try:
                start = date.fromisoformat(date_from)
                end = date.fromisoformat(date_to)
            except ValueError as exc:
                raise ValueError("date_from/date_to must use YYYY-MM-DD format") from exc
            if end < start:
                raise ValueError("date_to must be on or after date_from")
            # The captured UI range Nov 1–5 emitted 20261101–20261106,
            # so field 7 is the exclusive day after the inclusive UI end.
            filters["6"] = int(start.strftime("%Y%m%d"))
            filters["7"] = int((end + timedelta(days=1)).strftime("%Y%m%d"))
        payload: dict[str, Any] = {"2": page_size, "3": filters, "7": {"1": 1, "2": 0, "3": 2818}}
        if cursor is not None:
            payload["4"] = cursor
        data = await self._rpc("SearchService/SearchCreatives", payload)
        if not isinstance(data.get("1"), list):
            raise ResponseShapeError(f"SearchCreatives response missing list field '1'; got keys {list(data.keys())}")
        return self._model(CreativePage, data, "SearchCreatives")

    async def paginate(self, advertiser_id=None, region=None, date_from=None, date_to=None, *, domain=None, page_size=40) -> AsyncGenerator[Creative, None]:
        cursor: str | None = None
        while True:
            page = await self.list_creatives(advertiser_id=advertiser_id, region=region, date_from=date_from, date_to=date_to, cursor=cursor, domain=domain, page_size=page_size)
            for creative in page.creatives:
                yield creative
            if page.next_cursor is None:
                return
            cursor = page.next_cursor

    async def search_by_domain(self, domain: str, *, cursor: str | None = None, page_size: int = 40) -> CreativePage:
        return await self.list_creatives(domain=domain, cursor=cursor, page_size=page_size)

    async def get_advertiser_duns_mapping(self) -> list[DunsMappingEntry]:
        """Return every advertiser→DUNS entry in one shot. Cache the result; the upstream returns 6 000+ rows and is called on every page load by the site."""
        data = await self._rpc("TfaarAdvertiserService/GetAdvertiserDunsMapping", {})
        rows = data.get("1")
        if not isinstance(rows, list):
            raise ResponseShapeError(f"GetAdvertiserDunsMapping response missing list field '1'; got keys {list(data.keys())}")
        return [self._model(DunsMappingEntry, row, "GetAdvertiserDunsMapping") for row in rows]

    async def get_creative(self, advertiser_id: str, creative_id: str) -> CreativeDetail | None:
        data = await self._rpc("LookupService/GetCreativeById", {
            "1": advertiser_id,
            "2": creative_id,
            "5": {"1": 1, "2": 0, "3": 2818},
        })
        if not data:
            return None
        if not isinstance(data.get("1"), dict):
            raise ResponseShapeError(f"GetCreativeById response missing object field '1'; got keys {list(data.keys())}")
        return self._model(CreativeDetail, data["1"], "GetCreativeById")
