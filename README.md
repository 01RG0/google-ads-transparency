# ads-transparency-client

Typed async Python client for the Google Ads Transparency Center public RPC API (no authentication required).

## Installation

```bash
pip install -e .
```

Optional extras:

```bash
pip install -e ".[api]"   # FastAPI server + uvicorn
pip install -e ".[dev]"   # Test dependencies
```

## Quick start

```python
import asyncio
from client import TransparencyClient

async def main():
    async with TransparencyClient() as client:
        # Search advertisers
        advertisers = await client.search_advertisers("Nike", limit=10)
        advertiser_id = advertisers[0].advertiser_id

        # List creatives with region and date filters
        page = await client.list_creatives(
            advertiser_id=advertiser_id,
            region="US",
            date_from="2026-01-01",
            date_to="2026-12-31",
        )

        # Paginate all results automatically
        async for creative in client.paginate(advertiser_id=advertiser_id, region="US"):
            print(creative.creative_id, creative.domain)

        # Fetch a single creative detail
        detail = await client.get_creative(page.creatives[0].advertiser_id, page.creatives[0].creative_id)

        # Full advertiser → DUNS mapping (cache this; it returns 6000+ rows)
        duns = await client.get_advertiser_duns_mapping()

asyncio.run(main())
```

## Pagination

Manual cursor loop:

```python
async with TransparencyClient() as client:
    cursor = None
    while True:
        page = await client.list_creatives(advertiser_id="AR123", cursor=cursor)
        for creative in page.creatives:
            print(creative.creative_id, creative.advertiser_id)
        if not page.next_cursor:
            break
        cursor = page.next_cursor
```

Or use the built-in async generator:

```python
async with TransparencyClient() as client:
    async for creative in client.paginate(advertiser_id="AR123", region="GB"):
        print(creative.creative_id)
```

## Sync usage

```python
from client.sync_client import SyncTransparencyClient

with SyncTransparencyClient() as client:
    advertisers = client.search_advertisers("Nike")
    for creative in client.paginate(advertiser_id=advertisers[0].advertiser_id):
        print(creative.creative_id)
```

## CLI

```bash
python -m client search-advertisers Nike
python -m client search-advertisers Nike --limit 5
python -m client get-advertiser AR12345
python -m client list-creatives --advertiser AR12345 --region US --from 2026-01-01 --to 2026-12-31
python -m client list-creatives --domain nike.com --pages 3
```

## Available methods

| Method | Parameters | Returns |
|--------|------------|---------|
| `search_advertisers` | `query: str`, `limit: int = 10` | `list[AdvertiserSuggestion]` |
| `get_advertiser` | `advertiser_id: str` | `Advertiser \| None` |
| `list_creatives` | `advertiser_id`, `domain`, `region`, `date_from`, `date_to`, `cursor`, `page_size=40` | `CreativePage` |
| `search_by_domain` | `domain: str`, `cursor`, `page_size=40` | `CreativePage` |
| `paginate` | same as `list_creatives` minus `cursor` | `AsyncGenerator[Creative, None]` |
| `get_creative` | `advertiser_id: str`, `creative_id: str` | `CreativeDetail \| None` |
| `get_advertiser_duns_mapping` | — | `list[DunsMappingEntry]` |

`page_size` max is 40.

## Region filter

Accepts ISO 3166-1 alpha-2 codes (`US`, `GB`, `PS`) or official English country names (`United States`, `Palestine`). Pass `"anywhere"` or omit to get results from all regions. Iran is not available on the Transparency Center.

## Date filter

`date_from` and `date_to` are `YYYY-MM-DD` strings and must be supplied together. Providing only one raises `ValueError`.

## Error types

| Exception | When raised |
|-----------|-------------|
| `TransparencyError` | Base class for all client errors |
| `ResponseShapeError` | Upstream returned a shape outside the captured contract |
| `UnsupportedFilterError` | Filter value not supported (e.g. unknown country code) |
| `UpstreamHTTPError` | Non-2xx HTTP response after retries |

All exceptions are exported from `client.errors`.

## FastAPI server

```bash
pip install -e ".[api]"
uvicorn api.app:app --reload
```

Endpoints mirror the client methods as REST routes.

## Tests

```bash
# Contract and request-encoding tests (no network)
pytest -m "not live"

# Live smoke tests against the real API
ADS_TRANSPARENCY_LIVE=1 pytest -m live
```
