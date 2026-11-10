"""Command-line interface for the ads-transparency-client package.

Run with: python -m client
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from typing import Sequence

from .client import TransparencyClient
from .errors import TransparencyError


def _field(value: object | None) -> str:
    return "" if value is None else str(value)


def _print_table(columns: list[str], rows: list[list[str]]) -> None:
    widths = [len(col) for col in columns]
    for row in rows:
        for i, cell in enumerate(row):
            if len(cell) > widths[i]:
                widths[i] = len(cell)

    header = "  ".join(col.upper().ljust(widths[i]) for i, col in enumerate(columns))
    separator = "  ".join("-" * widths[i] for i in range(len(columns)))
    print(header)
    print(separator)
    for row in rows:
        print("  ".join(row[i].ljust(widths[i]) for i in range(len(columns))))


def _print_json(columns: list[str], rows: list[list[str]]) -> None:
    for row in rows:
        obj = {col: row[i] for i, col in enumerate(columns)}
        print(json.dumps(obj, ensure_ascii=False))


def _print_csv(columns: list[str], rows: list[list[str]]) -> None:
    writer = csv.writer(sys.stdout)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row)


def _output(columns: list[str], rows: list[list[str]], fmt: str) -> None:
    if fmt == "json":
        _print_json(columns, rows)
    elif fmt == "csv":
        _print_csv(columns, rows)
    else:
        _print_table(columns, rows)


async def _search_advertisers(client: TransparencyClient, args: argparse.Namespace) -> None:
    results = await client.search_advertisers(args.query, limit=args.limit)
    columns = ["advertiser_id", "name", "country_code"]
    rows = [
        [_field(result.advertiser_id), _field(result.name), _field(result.country_code)]
        for result in results
    ]
    _output(columns, rows, args.format)


async def _list_creatives(client: TransparencyClient, args: argparse.Namespace) -> None:
    columns = ["creative_id", "advertiser_id", "format_type", "domain"]
    rows: list[list[str]] = []
    cursor: str | None = None
    pages = 0
    while pages < args.pages:
        pages += 1
        if args.pages > 1 and args.format == "table":
            print(f"Fetching page {pages}...", file=sys.stderr)
        page = await client.list_creatives(
            advertiser_id=args.advertiser,
            region=args.region,
            date_from=args.date_from,
            date_to=args.date_to,
            cursor=cursor,
            domain=args.domain,
        )
        for creative in page.creatives:
            rows.append(
                [
                    _field(creative.creative_id),
                    _field(creative.advertiser_id),
                    _field(creative.format_type),
                    _field(creative.domain),
                ]
            )
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    _output(columns, rows, args.format)


async def _get_advertiser(client: TransparencyClient, args: argparse.Namespace) -> None:
    advertiser = await client.get_advertiser(args.advertiser_id)
    if advertiser is None:
        return
    columns = ["advertiser_id", "name", "country_code"]
    rows = [
        [_field(advertiser.advertiser_id), _field(advertiser.name), _field(advertiser.country_code)]
    ]
    _output(columns, rows, args.format)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="client", description="CLI for the ads-transparency-client package")
    subparsers = parser.add_subparsers(dest="command", required=True)

    format_help = "Output format: table (default), json, or csv"

    search = subparsers.add_parser("search-advertisers", help="Search advertisers by query")
    search.add_argument("query", help="Advertiser search query")
    search.add_argument("--limit", type=int, default=10, help="Maximum number of results (default: 10)")
    search.add_argument("--format", choices=["table", "json", "csv"], default="table", help=format_help)

    creatives = subparsers.add_parser("list-creatives", help="List creatives with optional filters")
    creatives.add_argument("--advertiser", help="Advertiser ID filter")
    creatives.add_argument("--domain", help="Domain filter")
    creatives.add_argument("--region", help="Region/country filter (ISO alpha-2 or country name)")
    creatives.add_argument("--from", dest="date_from", help="Start date (YYYY-MM-DD)")
    creatives.add_argument("--to", dest="date_to", help="End date (YYYY-MM-DD)")
    creatives.add_argument("--pages", type=int, default=1, help="Maximum pages to paginate (default: 1)")
    creatives.add_argument("--format", choices=["table", "json", "csv"], default="table", help=format_help)

    get = subparsers.add_parser("get-advertiser", help="Get an advertiser by ID")
    get.add_argument("advertiser_id", help="Advertiser ID")
    get.add_argument("--format", choices=["table", "json", "csv"], default="table", help=format_help)

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
