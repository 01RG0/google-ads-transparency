from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

from .client import TransparencyClient


async def download_previews(
    client: TransparencyClient,
    advertiser_id: str,
    output_dir: Path,
    *,
    limit: int = 50,
    pages: int = 3,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    cursor: str | None = None

    for _ in range(pages):
        if count >= limit:
            break

        page = await client.list_creatives(
            advertiser_id=advertiser_id, cursor=cursor, page_size=40
        )

        remaining = limit - count
        batch = page.creatives[:remaining]

        results = await asyncio.gather(
            *[client.get_creative(c.advertiser_id, c.creative_id) for c in batch],
            return_exceptions=True,
        )

        for creative, result in zip(batch, results):
            if isinstance(result, Exception):
                print(
                    f'warning: get_creative failed for {creative.creative_id}: {result}',
                    file=sys.stderr,
                )
                continue

            detail = result
            if detail is None:
                continue

            try:
                variation = detail.variations[0]
                preview_url = (
                    variation.content.preview_url
                    if variation.content is not None
                    else None
                )
            except (IndexError, AttributeError):
                preview_url = None

            if not preview_url:
                continue

            try:
                async with httpx.AsyncClient() as http:
                    response = await http.get(preview_url, follow_redirects=True)
            except Exception as exc:
                print(
                    f'warning: download failed for {creative.creative_id}: {exc}',
                    file=sys.stderr,
                )
                continue

            if response.status_code != 200:
                print(
                    f'warning: unexpected status {response.status_code} for {creative.creative_id}',
                    file=sys.stderr,
                )
                continue

            out_path = output_dir / f'{creative.creative_id}.jpg'
            out_path.write_bytes(response.content)
            count += 1
            print(f'Downloading {count}/{limit}...', end='\r', file=sys.stderr)

        cursor = page.next_cursor
        if cursor is None:
            break

    print('', file=sys.stderr)
    return count