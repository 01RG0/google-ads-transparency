"""Command-line interface for the ads-transparency-client package.

Run with: python -m client
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Sequence

from .client import TransparencyClient
from .errors import TransparencyError


def _field(value: object | None) -> str:
    return "" if value is None else str(value)


async def _search_advertisers(client: TransparencyClient, args: argparse.Namespace) -> None:
    results = await client.search_advertisers(args.query, limit=args.limit)
    for result in results:
        print(f"{_field(result.advertiser_id)}\t{_field(result.name)}\t{_field(result.country_code)}")


async def _list_creatives(client: TransparencyClient, args: argparse.Namespace) -> None:
    cursor: str | None = None
    pages = 0
    while pages < args.pages:
        page = await client.list_creatives(
            advertiser_id=args.advertiser,
            region=args.region,
            date_from=args.date_from,
            date_to=args.date_to,
            cursor=cursor,
            domain=args.domain,
        )
        for creative in page.creatives:
            print(
                f"{_field(creative.creative_id)}\t"
                f"{_field(creative.advertiser_id)}\t"
                f"{_field(creative.format_type)}\t"
                f"{_field(creative.domain)}"
            )
        if page.next_cursor is None:
            return
        cursor = page.next_cursor
        pages += 1


async def _get_advertiser(client: TransparencyClient, args: argparse.Namespace) -> None:
    advertiser = await client.get_advertiser(args.advertiser_id)
    if advertiser is None:
        return
    print(f"{_field(advertiser.advertiser_id)}\t{_field(advertiser.name)}\t{_field(advertiser.country_code)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="client", description="CLI for the ads-transparency-client package")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search-advertisers", help="Search advertisers by query")
    search.add_argument("query", help="Advertiser search query")
    search.add_argument("--limit", type=int, default=10, help="Maximum number of results (default: 10)")

    creatives = subparsers.add_parser("list-creatives", help="List creatives with optional filters")
    creatives.add_argument("--advertiser", help="Advertiser ID filter")
    creatives.add_argument("--domain", help="Domain filter")
    creatives.add_argument("--region", help="Region/country filter (ISO alpha-2 or country name)")
    creatives.add_argument("--from", dest="date_from", help="Start date (YYYY-MM-DD)")
    creatives.add_argument("--to", dest="date_to", help="End date (YYYY-MM-DD)")
    creatives.add_argument("--pages", type=int, default=1, help="Maximum pages to paginate (default: 1)")

    get = subparsers.add_parser("get-advertiser", help="Get an advertiser by ID")
    get.add_argument("advertiser_id", help="Advertiser ID")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    async def _run() -> None:
        async with TransparencyClient() as client:
            if args.command == "search-advertisers":
                await _search_advertisers(client, args)
            elif args.command == "list-creatives":
                await _list_creatives(client, args)
            elif args.command == "get-advertiser":
                await _get_advertiser(client, args)

    try:
        asyncio.run(_run())
    except Exception as exc:  # CLI boundary: report any failure on stderr and exit 1
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
