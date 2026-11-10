"""Command-line interface for the ads-transparency-client package.

Run with: python -m client
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import csv
import json
import sys
from pathlib import Path
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
        print(json.dumps({col: row[i] for i, col in enumerate(columns)}, ensure_ascii=False))


def _print_csv(columns: list[str], rows: list[list[str]]) -> None:
    writer = csv.writer(sys.stdout)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row)


def _print_xlsx(columns: list[str], rows: list[list[str]], filename: str) -> None:
    try:
        import openpyxl  # type: ignore[import-untyped]
    except ImportError:
        print("Error: install openpyxl first:  pip install openpyxl", file=sys.stderr)
        sys.exit(1)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([c.upper() for c in columns])
    for row in rows:
        ws.append(row)
    wb.save(filename)
    print(f"Saved {len(rows)} rows to {filename}", file=sys.stderr)


def _output(columns: list[str], rows: list[list[str]], fmt: str, output_file: str = "output.xlsx") -> None:
    if fmt == "json":
        _print_json(columns, rows)
    elif fmt == "csv":
        _print_csv(columns, rows)
    elif fmt == "xlsx":
        _print_xlsx(columns, rows, output_file)
    else:
        _print_table(columns, rows)


# ── existing commands ──────────────────────────────────────────────────────────

async def _search_advertisers(client: TransparencyClient, args: argparse.Namespace) -> None:
    results = await client.search_advertisers(args.query, limit=args.limit)
    columns = ["advertiser_id", "name", "country_code"]
    rows = [
        [_field(r.advertiser_id), _field(r.name), _field(r.country_code)]
        for r in results
    ]
    _output(columns, rows, args.format, args.output)


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
            rows.append([
                _field(creative.creative_id),
                _field(creative.advertiser_id),
                _field(creative.format_type),
                _field(creative.domain),
            ])
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    _output(columns, rows, args.format, args.output)


async def _get_advertiser(client: TransparencyClient, args: argparse.Namespace) -> None:
    advertiser = await client.get_advertiser(args.advertiser_id)
    if advertiser is None:
        return
    columns = ["advertiser_id", "name", "country_code"]
    rows = [[_field(advertiser.advertiser_id), _field(advertiser.name), _field(advertiser.country_code)]]
    _output(columns, rows, args.format, args.output)


# ── new commands ───────────────────────────────────────────────────────────────

async def _find_advertisers(client: TransparencyClient, args: argparse.Namespace) -> None:
    seen: set[str] = set()
    rows: list[list[str]] = []
    columns = ["advertiser_id", "name", "country_code", "matched_keyword"]
    for kw in args.keywords:
        results = await client.search_advertisers(kw, limit=args.limit)
        for r in results:
            if r.advertiser_id and r.advertiser_id not in seen:
                seen.add(r.advertiser_id)
                rows.append([_field(r.advertiser_id), _field(r.name), _field(r.country_code), kw])
    _output(columns, rows, args.format, args.output)


async def _discover_competitors(client: TransparencyClient, args: argparse.Namespace) -> None:
    page = await client.search_by_domain(args.domain, page_size=40)
    seen: set[str] = set()
    rows: list[list[str]] = []
    columns = ["advertiser_id", "name", "country_code"]
    for creative in page.creatives:
        aid = creative.advertiser_id
        if aid and aid not in seen:
            seen.add(aid)
            adv = await client.get_advertiser(aid)
            if adv:
                rows.append([_field(adv.advertiser_id), _field(adv.name), _field(adv.country_code)])
    _output(columns, rows, args.format, args.output)


_FORMAT_NAMES = {1: "Display", 2: "Video", 3: "Search", 0: "Unknown"}


async def _collect_stats(client: TransparencyClient, advertiser_id: str, pages: int):
    format_counts: collections.Counter[int] = collections.Counter()
    domains: collections.Counter[str] = collections.Counter()
    earliest = None
    latest = None
    total_count = None
    sampled = 0
    cursor: str | None = None
    for _ in range(pages):
        page = await client.list_creatives(advertiser_id=advertiser_id, cursor=cursor)
        if total_count is None:
            total_count = page.total_count
        for c in page.creatives:
            sampled += 1
            format_counts[c.format_type or 0] += 1
            if c.domain:
                domains[c.domain] += 1
            if c.first_shown and c.first_shown.seconds:
                dt = c.first_shown.to_datetime()
                if dt and (earliest is None or dt < earliest):
                    earliest = dt
            if c.last_shown and c.last_shown.seconds:
                dt = c.last_shown.to_datetime()
                if dt and (latest is None or dt > latest):
                    latest = dt
        if not page.next_cursor:
            break
        cursor = page.next_cursor
    return total_count, format_counts, domains, sampled, earliest, latest


async def _advertiser_stats(client: TransparencyClient, args: argparse.Namespace) -> None:
    adv = await client.get_advertiser(args.advertiser_id)
    if adv is None:
        print("Advertiser not found", file=sys.stderr)
        return
    total_count, fc, domains, sampled, earliest, latest = await _collect_stats(
        client, args.advertiser_id, args.pages
    )
    print(f"Advertiser:   {adv.name} ({adv.advertiser_id})")
    print(f"Country:      {adv.country_code or '-'}")
    print(f"Total ads:    {total_count or 'unknown'}")
    print(f"Sampled:      {sampled} creatives ({args.pages} page(s))")
    print()
    print("Format breakdown (from sample):")
    for ft, name in _FORMAT_NAMES.items():
        count = fc.get(ft, 0)
        if count:
            pct = round(100 * count / sampled) if sampled else 0
            print(f"  {name:<10} {count:>5}  ({pct}%)")
    print()
    if domains:
        print("Top domains (from sample):")
        for domain, cnt in domains.most_common(5):
            print(f"  {domain:<40} {cnt}")
        print()
    fmt_dt = lambda dt: dt.strftime("%Y-%m-%d") if dt else "-"
    if earliest or latest:
        print("Date range (from sample):")
        print(f"  Earliest first_shown: {fmt_dt(earliest)}")
        print(f"  Latest  last_shown:   {fmt_dt(latest)}")


async def _compare_advertisers(client: TransparencyClient, args: argparse.Namespace) -> None:
    adv1 = await client.get_advertiser(args.id1)
    adv2 = await client.get_advertiser(args.id2)
    tc1, fc1, _, s1, e1, l1 = await _collect_stats(client, args.id1, args.pages)
    tc2, fc2, _, s2, e2, l2 = await _collect_stats(client, args.id2, args.pages)

    name1 = ((adv1.name if adv1 else None) or args.id1)[:22]
    name2 = ((adv2.name if adv2 else None) or args.id2)[:22]
    w = 22
    print(f"{'Metric':<26}  {name1:<{w}}  {name2}")
    print("-" * (26 + 2 + w + 2 + w))
    print(f"{'Total ads':<26}  {str(tc1 or '?'):<{w}}  {tc2 or '?'}")

    def pct(fc: collections.Counter[int], ft: int, total: int) -> str:
        return f"{round(100 * fc.get(ft, 0) / total)}%" if total else "-"

    for ft, name in _FORMAT_NAMES.items():
        if fc1.get(ft, 0) or fc2.get(ft, 0):
            label = f"{name} %"
            print(f"{label:<26}  {pct(fc1, ft, s1):<{w}}  {pct(fc2, ft, s2)}")

    fmt_dt = lambda dt: dt.strftime("%Y-%m-%d") if dt else "-"
    print(f"{'Earliest ad':<26}  {fmt_dt(e1):<{w}}  {fmt_dt(e2)}")
    print(f"{'Latest ad':<26}  {fmt_dt(l1):<{w}}  {fmt_dt(l2)}")


async def _download_previews(client: TransparencyClient, args: argparse.Namespace) -> None:
    from .downloader import download_previews as _dl
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    count = await _dl(client, args.advertiser_id, out, limit=args.limit, pages=args.pages)
    print(f"Downloaded {count} preview images to {out}", file=sys.stderr)


# ── parser ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="client", description="CLI for the ads-transparency-client package")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fmt_help = "Output format: table (default), json, csv, or xlsx"
    fmt_choices = ["table", "json", "csv", "xlsx"]

    # search-advertisers
    search = subparsers.add_parser("search-advertisers", help="Search advertisers by query")
    search.add_argument("query", help="Advertiser search query")
    search.add_argument("--limit", type=int, default=10, help="Maximum results (default 10)")
    search.add_argument("--format", choices=fmt_choices, default="table", help=fmt_help)
    search.add_argument("--output", default="output.xlsx", help="Output file for xlsx format")

    # list-creatives
    creatives = subparsers.add_parser("list-creatives", help="List creatives with optional filters")
    creatives.add_argument("--advertiser", help="Advertiser ID filter")
    creatives.add_argument("--domain", help="Domain filter")
    creatives.add_argument("--region", help="Region filter (ISO alpha-2 or country name)")
    creatives.add_argument("--from", dest="date_from", help="Start date (YYYY-MM-DD)")
    creatives.add_argument("--to", dest="date_to", help="End date (YYYY-MM-DD)")
    creatives.add_argument("--pages", type=int, default=1, help="Max pages to paginate (default 1)")
    creatives.add_argument("--format", choices=fmt_choices, default="table", help=fmt_help)
    creatives.add_argument("--output", default="output.xlsx", help="Output file for xlsx format")

    # get-advertiser
    get = subparsers.add_parser("get-advertiser", help="Get an advertiser by ID")
    get.add_argument("advertiser_id", help="Advertiser ID")
    get.add_argument("--format", choices=fmt_choices, default="table", help=fmt_help)
    get.add_argument("--output", default="output.xlsx", help="Output file for xlsx format")

    # find-advertisers
    find = subparsers.add_parser("find-advertisers", help="Search by multiple keywords, deduplicated")
    find.add_argument("keywords", nargs="+", help="One or more search keywords")
    find.add_argument("--limit", type=int, default=10, help="Results per keyword (default 10)")
    find.add_argument("--format", choices=fmt_choices, default="table", help=fmt_help)
    find.add_argument("--output", default="output.xlsx", help="Output file for xlsx format")

    # discover-competitors
    disc = subparsers.add_parser("discover-competitors", help="Find advertisers running ads on a domain")
    disc.add_argument("domain", help="Domain to search (e.g. nike.com)")
    disc.add_argument("--format", choices=fmt_choices, default="table", help=fmt_help)
    disc.add_argument("--output", default="output.xlsx", help="Output file for xlsx format")

    # advertiser-stats
    stats = subparsers.add_parser("advertiser-stats", help="Show statistics for an advertiser")
    stats.add_argument("advertiser_id", help="Advertiser ID (AR...)")
    stats.add_argument("--pages", type=int, default=3, help="Pages to sample (default 3)")

    # compare-advertisers
    cmp = subparsers.add_parser("compare-advertisers", help="Compare two advertisers side by side")
    cmp.add_argument("id1", help="First advertiser ID")
    cmp.add_argument("id2", help="Second advertiser ID")
    cmp.add_argument("--pages", type=int, default=3, help="Pages to sample per advertiser (default 3)")

    # download-previews
    dl = subparsers.add_parser("download-previews", help="Download ad preview images for an advertiser")
    dl.add_argument("advertiser_id", help="Advertiser ID (AR...)")
    dl.add_argument("--output", default="./previews", help="Output directory (default ./previews)")
    dl.add_argument("--limit", type=int, default=50, help="Max images to download (default 50)")
    dl.add_argument("--pages", type=int, default=3, help="Pages of creatives to scan (default 3)")

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
            elif args.command == "find-advertisers":
                await _find_advertisers(client, args)
            elif args.command == "discover-competitors":
                await _discover_competitors(client, args)
            elif args.command == "advertiser-stats":
                await _advertiser_stats(client, args)
            elif args.command == "compare-advertisers":
                await _compare_advertisers(client, args)
            elif args.command == "download-previews":
                await _download_previews(client, args)

    try:
        asyncio.run(_run())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
