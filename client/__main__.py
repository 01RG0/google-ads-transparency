"""Command-line interface for the ads-transparency-client package.

Run with: python -m client
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import csv
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from .ai import ai_complete, list_providers
from .client import TransparencyClient
from .config import get as _cfg, get_config, write_sample_config, write_sample_env
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
    links = getattr(args, "links", False)
    columns = ["advertiser_id", "name", "country_code"] + (["transparency_url"] if links else [])
    rows = [
        [_field(r.advertiser_id), _field(r.name), _field(r.country_code)]
        + ([_field(r.transparency_url)] if links else [])
        for r in results
    ]
    _output(columns, rows, args.format, args.output)


async def _list_creatives(client: TransparencyClient, args: argparse.Namespace) -> None:
    links = getattr(args, "links", False)
    columns = ["creative_id", "advertiser_id", "format_type", "domain"] + (
        ["transparency_url", "domain_url"] if links else []
    )
    rows: list[list[str]] = []
    cursor: str | None = None
    all_pages: bool = getattr(args, "all_pages", False)
    max_pages: int = 999_999 if all_pages else args.pages
    pages = 0
    while pages < max_pages:
        pages += 1
        if (all_pages or args.pages > 1) and args.format == "table":
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
            row = [
                _field(creative.creative_id),
                _field(creative.advertiser_id),
                _field(creative.format_type),
                _field(creative.domain),
            ]
            if links:
                row += [_field(creative.transparency_url), _field(creative.domain_url)]
            rows.append(row)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    _output(columns, rows, args.format, args.output)


async def _get_advertiser(client: TransparencyClient, args: argparse.Namespace) -> None:
    advertiser = await client.get_advertiser(args.advertiser_id)
    if advertiser is None:
        return
    links = getattr(args, "links", False)
    columns = ["advertiser_id", "name", "country_code"] + (["transparency_url"] if links else [])
    rows = [[_field(advertiser.advertiser_id), _field(advertiser.name), _field(advertiser.country_code)]
            + ([_field(advertiser.transparency_url)] if links else [])]
    _output(columns, rows, args.format, args.output)


# ── new commands ───────────────────────────────────────────────────────────────

async def _find_advertisers(client: TransparencyClient, args: argparse.Namespace) -> None:
    links = getattr(args, "links", False)
    seen: set[str] = set()
    rows: list[list[str]] = []
    columns = ["advertiser_id", "name", "country_code", "matched_keyword"] + (["transparency_url"] if links else [])
    for kw in args.keywords:
        results = await client.search_advertisers(kw, limit=args.limit)
        for r in results:
            if r.advertiser_id and r.advertiser_id not in seen:
                seen.add(r.advertiser_id)
                row = [_field(r.advertiser_id), _field(r.name), _field(r.country_code), kw]
                if links:
                    row.append(_field(r.transparency_url))
                rows.append(row)
    _output(columns, rows, args.format, args.output)


async def _discover_competitors(client: TransparencyClient, args: argparse.Namespace) -> None:
    links = getattr(args, "links", False)
    page = await client.search_by_domain(args.domain, page_size=40)
    seen: set[str] = set()
    rows: list[list[str]] = []
    columns = ["advertiser_id", "name", "country_code"] + (["transparency_url"] if links else [])
    for creative in page.creatives:
        aid = creative.advertiser_id
        if aid and aid not in seen:
            seen.add(aid)
            adv = await client.get_advertiser(aid)
            if adv:
                row = [_field(adv.advertiser_id), _field(adv.name), _field(adv.country_code)]
                if links:
                    row.append(_field(adv.transparency_url))
                rows.append(row)
    _output(columns, rows, args.format, args.output)


_FORMAT_NAMES = {1: "Display", 2: "Video", 3: "Search", 0: "Unknown"}


async def _collect_stats(client: TransparencyClient, advertiser_id: str, pages: int):
    format_counts: collections.Counter[int] = collections.Counter()
    domains: collections.Counter[str] = collections.Counter()
    monthly: collections.Counter[str] = collections.Counter()
    earliest = None
    latest = None
    total_count = None
    sampled = 0
    region_total = 0
    region_items = 0
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
            if c.region_count is not None:
                region_total += c.region_count
                region_items += 1
            if c.first_shown and c.first_shown.seconds:
                dt = c.first_shown.to_datetime()
                if dt and (earliest is None or dt < earliest):
                    earliest = dt
            if c.last_shown and c.last_shown.seconds:
                dt = c.last_shown.to_datetime()
                if dt and (latest is None or dt > latest):
                    latest = dt
                    monthly[dt.strftime("%Y-%m")] += 1
        if not page.next_cursor:
            break
        cursor = page.next_cursor
    avg_region = region_total / region_items if region_items else 0.0
    # detect trend from monthly distribution
    sorted_months = sorted(monthly)
    if len(sorted_months) >= 6:
        third = max(1, len(sorted_months) // 3)
        early = sum(monthly[m] for m in sorted_months[:third]) / third
        late = sum(monthly[m] for m in sorted_months[-third:]) / third
        trend = "increasing" if late > early * 1.2 else "decreasing" if late < early * 0.8 else "stable"
    else:
        trend = "unknown (insufficient sample)"
    return total_count, format_counts, domains, sampled, earliest, latest, monthly, avg_region, trend


async def _advertiser_stats(client: TransparencyClient, args: argparse.Namespace) -> None:
    adv = await client.get_advertiser(args.advertiser_id)
    if adv is None:
        print("Advertiser not found", file=sys.stderr)
        return
    total_count, fc, domains, sampled, earliest, latest, monthly, avg_region, trend = \
        await _collect_stats(client, args.advertiser_id, args.pages)
    fmt_dt = lambda dt: dt.strftime("%Y-%m-%d") if dt else "-"
    print(f"Advertiser:      {adv.name} ({adv.advertiser_id})")
    print(f"Country:         {adv.country_code or '-'}")
    print(f"Total ads:       {total_count or 'unknown'}")
    print(f"Sampled:         {sampled} creatives ({args.pages} page(s))")
    if avg_region:
        print(f"Avg regions/ad:  {avg_region:.0f}")
    print(f"Activity trend:  {trend}")
    print()
    print("Format breakdown:")
    for ft, name in _FORMAT_NAMES.items():
        count = fc.get(ft, 0)
        if count:
            pct = round(100 * count / sampled) if sampled else 0
            print(f"  {name:<10} {count:>5}  ({pct}%)")
    print()
    if domains:
        print("Top domains:")
        for domain, cnt in domains.most_common(5):
            print(f"  {domain:<40} {cnt}")
        print()
    if earliest or latest:
        print(f"Date range:      {fmt_dt(earliest)} → {fmt_dt(latest)}")
    if monthly:
        peak = sorted(monthly, key=monthly.get, reverse=True)[:3]
        print(f"Peak months:     {', '.join(peak)}")


async def _compare_advertisers(client: TransparencyClient, args: argparse.Namespace) -> None:
    adv1 = await client.get_advertiser(args.id1)
    adv2 = await client.get_advertiser(args.id2)
    tc1, fc1, _, s1, e1, l1, *_ = await _collect_stats(client, args.id1, args.pages)
    tc2, fc2, _, s2, e2, l2, *_ = await _collect_stats(client, args.id2, args.pages)

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


def _ai_args(sub: argparse.ArgumentParser) -> None:
    default_provider = _cfg("ai", "provider") or os.environ.get("AI_PROVIDER") or "groq"
    default_model = _cfg("ai", "model") or os.environ.get("AI_MODEL") or None
    sub.add_argument("--provider", default=default_provider,
                     help=f"AI provider: {', '.join(list_providers())}, or custom (default: {default_provider})")
    sub.add_argument("--model", default=default_model,
                     help="Model name (auto-detected if omitted)")
    sub.add_argument("--api-key", dest="api_key", default=None,
                     help="API key (uses env variable if omitted)")
    sub.add_argument("--base-url", dest="base_url", default=None,
                     help="Base URL for custom/self-hosted providers")


async def _summarize_advertiser(client: TransparencyClient, args: argparse.Namespace) -> None:
    adv = await client.get_advertiser(args.advertiser_id)
    if adv is None:
        print("Advertiser not found", file=sys.stderr)
        return
    total_count, fc, domains, sampled, earliest, latest, monthly, avg_region, trend = \
        await _collect_stats(client, args.advertiser_id, args.pages)
    fmt_dt = lambda dt: dt.strftime("%Y-%m-%d") if dt else "unknown"
    peak_months = sorted(monthly, key=monthly.get, reverse=True)[:3] if monthly else []
    fmt_lines = [
        f"  {_FORMAT_NAMES.get(ft, 'Unknown')}: {round(100*cnt/sampled)}%"
        for ft, cnt in sorted(fc.items(), key=lambda x: -x[1]) if sampled and cnt
    ]
    data = "\n".join([
        f"Advertiser: {adv.name}",
        f"Registered country: {adv.country_code or 'unknown'}",
        f"Total ads in database: ~{total_count or 'unknown'}",
        f"Sample analyzed: {sampled} creatives ({args.pages} page(s))",
        f"Format mix (from sample):\n" + "\n".join(fmt_lines),
        f"Average geographic reach per ad: {avg_region:.0f} regions",
        f"Top advertised domains: {', '.join(d for d, _ in domains.most_common(5))}",
        f"Activity period: {fmt_dt(earliest)} to {fmt_dt(latest)}",
        f"Monthly activity trend: {trend}",
        f"Peak activity months: {', '.join(peak_months) or 'unknown'}",
    ])
    prompt = (
        f"You are a senior marketing analyst. Analyze this Google Ads Transparency Center "
        f"data and provide a structured competitive intelligence report.\n\n"
        f"DATA:\n{data}\n\n"
        "Provide your analysis in this exact format:\n\n"
        "## Executive Summary\n"
        "[2-3 sentences capturing the core advertising strategy and market position]\n\n"
        "## Format Strategy\n"
        "[What the format mix reveals about their funnel, goals, and audience targeting]\n\n"
        "## Geographic Reach\n"
        f"[What {avg_region:.0f} avg regions per ad + country of registration reveals about targeting strategy]\n\n"
        "## Activity Patterns\n"
        "[Seasonality, trend direction, and what it implies about their business cycles]\n\n"
        "## Competitive Implications\n"
        "[What a direct competitor should know and how they should respond]\n\n"
        "## 3 Actionable Recommendations\n"
        "[Numbered, specific recommendations for a marketer analyzing this data]"
    )
    print(f"Analyzing {adv.name} ({sampled} creatives) with {args.provider}...", file=sys.stderr)
    print(await ai_complete(prompt, provider=args.provider, model=args.model,
                            api_key=args.api_key, base_url=args.base_url))


async def _smart_compare(client: TransparencyClient, args: argparse.Namespace) -> None:
    adv1 = await client.get_advertiser(args.id1)
    adv2 = await client.get_advertiser(args.id2)
    r1 = await _collect_stats(client, args.id1, args.pages)
    r2 = await _collect_stats(client, args.id2, args.pages)
    tc1, fc1, dom1, s1, e1, l1, mo1, ar1, tr1 = r1
    tc2, fc2, dom2, s2, e2, l2, mo2, ar2, tr2 = r2
    fmt_dt = lambda dt: dt.strftime("%Y-%m-%d") if dt else "unknown"

    def _block(adv, aid, tc, fc, dom, s, e, l, ar, tr) -> str:
        name = (adv.name if adv else aid) or aid
        country = adv.country_code if adv else "unknown"
        lines = [
            f"Name: {name} (country: {country})",
            f"Total ads in database: ~{tc or 'unknown'}",
            f"Sample: {s} creatives",
        ]
        if s:
            for ft, fn in _FORMAT_NAMES.items():
                pct = round(100 * fc.get(ft, 0) / s)
                if pct:
                    lines.append(f"  {fn}: {pct}%")
        lines.append(f"Avg geographic reach: {ar:.0f} regions per ad")
        if dom:
            lines.append(f"Top domains: {', '.join(d for d, _ in dom.most_common(3))}")
        lines.append(f"Active: {fmt_dt(e)} to {fmt_dt(l)}")
        lines.append(f"Activity trend: {tr}")
        return "\n".join(f"  {x}" for x in lines)

    name1 = (adv1.name if adv1 else args.id1) or args.id1
    name2 = (adv2.name if adv2 else args.id2) or args.id2
    prompt = (
        "You are a senior competitive intelligence analyst. Compare these two advertisers "
        "based on Google Ads Transparency Center data.\n\n"
        f"## Advertiser A\n{_block(adv1, args.id1, tc1, fc1, dom1, s1, e1, l1, ar1, tr1)}\n\n"
        f"## Advertiser B\n{_block(adv2, args.id2, tc2, fc2, dom2, s2, e2, l2, ar2, tr2)}\n\n"
        "Provide your analysis in this exact format:\n\n"
        "## Head-to-Head Summary\n"
        "[2-3 sentences on who is winning and why]\n\n"
        "## Key Strategic Differences\n"
        "[Format, reach, timing, and domain strategy differences]\n\n"
        "## Aggression & Investment\n"
        "[Who is investing more, scaling faster, or taking more risks]\n\n"
        "## What A Can Learn from B\n"
        "[Specific tactics or strategies to adopt]\n\n"
        "## What B Can Learn from A\n"
        "[Specific tactics or strategies to adopt]\n\n"
        "## 3 Recommended Actions\n"
        "[For a marketer who wants to outperform both advertisers]"
    )
    print(f"Comparing {name1} vs {name2} with {args.provider}...", file=sys.stderr)
    print(await ai_complete(prompt, provider=args.provider, model=args.model,
                            api_key=args.api_key, base_url=args.base_url))


async def _suggest_keywords(client: TransparencyClient, args: argparse.Namespace) -> None:
    # Fetch 3 pages for richer domain/format signal
    all_domains: collections.Counter[str] = collections.Counter()
    fc: collections.Counter[int] = collections.Counter()
    total_count = None
    cursor: str | None = None
    for _ in range(3):
        page = await client.list_creatives(domain=args.domain, page_size=40, cursor=cursor)
        if total_count is None:
            total_count = page.total_count
        for c in page.creatives:
            if c.domain:
                all_domains[c.domain] += 1
            fc[c.format_type or 0] += 1
        if not page.next_cursor:
            break
        cursor = page.next_cursor
    sampled = sum(fc.values())
    fmt_mix = ", ".join(
        f"{_FORMAT_NAMES.get(ft,'?')}: {round(100*cnt/sampled)}%"
        for ft, cnt in sorted(fc.items(), key=lambda x: -x[1]) if sampled and cnt
    )
    top_domains = [d for d, _ in all_domains.most_common(15)]
    data = "\n".join([
        f"Target domain: {args.domain}",
        f"Total ads in database for this domain: ~{total_count or 'unknown'}",
        f"Sample analyzed: {sampled} creatives",
        f"Format mix: {fmt_mix}",
        f"Related/advertised domains ({len(top_domains)} found): {', '.join(top_domains)}",
    ])
    prompt = (
        f"You are a PPC and SEO keyword strategist. A client wants to compete with or "
        f"complement advertisers running ads on '{args.domain}' "
        f"(data from Google Ads Transparency Center).\n\n"
        f"DATA:\n{data}\n\n"
        "Provide your keyword strategy in this exact format:\n\n"
        "## Competitor Brand Keywords\n"
        "[Brand + competitor terms to bid on]\n\n"
        "## Product/Service Keywords\n"
        "[Core product terms based on the domain and related domains]\n\n"
        "## Intent-Based Keywords\n"
        "[High-intent transactional terms grouped by funnel stage]\n\n"
        "## Long-Tail Opportunities\n"
        "[Specific low-competition, high-conversion phrases]\n\n"
        "## Negative Keywords to Exclude\n"
        "[Terms to exclude to protect budget]\n\n"
        "## Bidding Priority Order\n"
        "[Which group to invest in first and why]"
    )
    print(f"Analyzing {args.domain} with {args.provider}...", file=sys.stderr)
    print(await ai_complete(prompt, provider=args.provider, model=args.model,
                            api_key=args.api_key, base_url=args.base_url))


def _config_init(args: argparse.Namespace) -> None:
    target = Path.home() / ".config" / "ads-transparency" if getattr(args, "global_", False) else Path(".")
    target.mkdir(parents=True, exist_ok=True)
    cfg_path = target / ("config.toml" if getattr(args, "global_", False) else "ads-transparency.toml")
    env_path = target / (".ads-transparency.env" if getattr(args, "global_", False) else ".env")
    if not cfg_path.exists():
        write_sample_config(cfg_path)
        print(f"Created {cfg_path}")
    else:
        print(f"Already exists: {cfg_path}")
    if not env_path.exists():
        write_sample_env(env_path)
        print(f"Created {env_path}")
    else:
        print(f"Already exists: {env_path}")
    if not getattr(args, "global_", False):
        print()
        print("⚠  Add these lines to .gitignore so you never commit secrets:")
        print("   ads-transparency.toml")
        print("   .env")


def _config_show() -> None:
    import pprint
    cfg = get_config()
    if cfg:
        pprint.pprint(cfg)
    else:
        print("No config file found. Run:  python -m client config init")
    print()
    ai_keys = ["GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "TOGETHER_API_KEY",
               "AI_PROVIDER", "AI_MODEL", "AI_API_KEY", "AI_BASE_URL"]
    print("Active environment variables:")
    for k in ai_keys:
        v = os.environ.get(k)
        if v:
            masked = v[:6] + "..." + v[-4:] if len(v) > 12 else "***"
            print(f"  {k} = {masked}")


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
    search.add_argument("--links", action="store_true", help="Add Transparency Center URL column")

    # list-creatives
    creatives = subparsers.add_parser("list-creatives", help="List creatives with optional filters")
    creatives.add_argument("--advertiser", help="Advertiser ID filter")
    creatives.add_argument("--domain", help="Domain filter")
    creatives.add_argument("--region", help="Region filter (ISO alpha-2 or country name)")
    creatives.add_argument("--from", dest="date_from", help="Start date (YYYY-MM-DD)")
    creatives.add_argument("--to", dest="date_to", help="End date (YYYY-MM-DD)")
    creatives.add_argument("--pages", type=int, default=1, help="Max pages to paginate (default 1)")
    creatives.add_argument("--all-pages", dest="all_pages", action="store_true", help="Fetch all pages (overrides --pages)")
    creatives.add_argument("--links", action="store_true", help="Add Transparency Center URL and domain URL columns")
    creatives.add_argument("--format", choices=fmt_choices, default="table", help=fmt_help)
    creatives.add_argument("--output", default="output.xlsx", help="Output file for xlsx format")

    # get-advertiser
    get = subparsers.add_parser("get-advertiser", help="Get an advertiser by ID")
    get.add_argument("advertiser_id", help="Advertiser ID")
    get.add_argument("--links", action="store_true", help="Add Transparency Center URL column")
    get.add_argument("--format", choices=fmt_choices, default="table", help=fmt_help)
    get.add_argument("--output", default="output.xlsx", help="Output file for xlsx format")

    # find-advertisers
    find = subparsers.add_parser("find-advertisers", help="Search by multiple keywords, deduplicated")
    find.add_argument("keywords", nargs="+", help="One or more search keywords")
    find.add_argument("--limit", type=int, default=10, help="Results per keyword (default 10)")
    find.add_argument("--links", action="store_true", help="Add Transparency Center URL column")
    find.add_argument("--format", choices=fmt_choices, default="table", help=fmt_help)
    find.add_argument("--output", default="output.xlsx", help="Output file for xlsx format")

    # discover-competitors
    disc = subparsers.add_parser("discover-competitors", help="Find advertisers running ads on a domain")
    disc.add_argument("domain", help="Domain to search (e.g. nike.com)")
    disc.add_argument("--links", action="store_true", help="Add Transparency Center URL column")
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

    # summarize-advertiser
    summ = subparsers.add_parser("summarize-advertiser", help="AI summary of an advertiser's strategy")
    summ.add_argument("advertiser_id", help="Advertiser ID (AR...)")
    summ.add_argument("--pages", type=int, default=3, help="Pages to sample (default 3)")
    _ai_args(summ)

    # smart-compare
    sc = subparsers.add_parser("smart-compare", help="AI-powered comparison of two advertisers")
    sc.add_argument("id1", help="First advertiser ID")
    sc.add_argument("id2", help="Second advertiser ID")
    sc.add_argument("--pages", type=int, default=3, help="Pages to sample per advertiser (default 3)")
    _ai_args(sc)

    # suggest-keywords
    sk = subparsers.add_parser("suggest-keywords", help="AI keyword suggestions based on a domain")
    sk.add_argument("domain", help="Domain to research (e.g. nike.com)")
    _ai_args(sk)

    # config
    cfg_p = subparsers.add_parser("config", help="Manage configuration files")
    cfg_sub = cfg_p.add_subparsers(dest="config_command", required=True)
    cfg_init = cfg_sub.add_parser("init", help="Create sample config and .env files")
    cfg_init.add_argument("--global", dest="global_", action="store_true",
                          help="Write to ~/.config/ads-transparency/ instead of current directory")
    cfg_sub.add_parser("show", help="Show current config and active API keys")

    # download-previews
    dl = subparsers.add_parser("download-previews", help="Download ad preview images for an advertiser")
    dl.add_argument("advertiser_id", help="Advertiser ID (AR...)")
    dl.add_argument("--output", default="./previews", help="Output directory (default ./previews)")
    dl.add_argument("--limit", type=int, default=50, help="Max images to download (default 50)")
    dl.add_argument("--pages", type=int, default=3, help="Pages of creatives to scan (default 3)")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    get_config()  # load .env + config file into os.environ before argparse reads env
    parser = build_parser()
    args = parser.parse_args(argv)

    # config commands don't need a live client
    if args.command == "config":
        if args.config_command == "init":
            _config_init(args)
        elif args.config_command == "show":
            _config_show()
        return 0

    _timeout = _cfg("client", "timeout", 20)
    _interval = _cfg("client", "min_interval", 0.25)
    _retries = _cfg("client", "max_retries", 3)
    _proxy = _cfg("client", "proxy") or None

    async def _run() -> None:
        async with TransparencyClient(
            timeout=_timeout, min_interval=_interval, max_retries=_retries, proxy=_proxy
        ) as client:
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
            elif args.command == "summarize-advertiser":
                await _summarize_advertiser(client, args)
            elif args.command == "smart-compare":
                await _smart_compare(client, args)
            elif args.command == "suggest-keywords":
                await _suggest_keywords(client, args)
            elif args.command == "download-previews":
                await _download_previews(client, args)

    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        asyncio.run(_run())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
