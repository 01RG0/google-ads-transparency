from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB = Path('ads-transparency.db')


def init_db(path: Path = DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS creatives (
            creative_id TEXT PRIMARY KEY,
            advertiser_id TEXT,
            advertiser_name TEXT,
            format_type INTEGER,
            domain TEXT,
            first_shown TEXT,
            last_shown TEXT,
            region_count INTEGER,
            transparency_url TEXT,
            domain_url TEXT,
            fetched_at TEXT,
            source TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS advertisers (
            advertiser_id TEXT PRIMARY KEY,
            name TEXT,
            country_code TEXT,
            platform_names TEXT,
            transparency_url TEXT,
            fetched_at TEXT,
            source TEXT
        )
        """
    )
    conn.commit()
    return conn


def save_creatives(conn: sqlite3.Connection, creatives: list, source: str = '') -> int:
    fetched_at = datetime.now(timezone.utc).isoformat()
    count = 0
    for creative in creatives:
        first_shown = (
            creative.first_shown.to_datetime().isoformat()
            if creative.first_shown is not None
            else None
        )
        last_shown = (
            creative.last_shown.to_datetime().isoformat()
            if creative.last_shown is not None
            else None
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO creatives (
                creative_id, advertiser_id, advertiser_name, format_type, domain,
                first_shown, last_shown, region_count, transparency_url, domain_url,
                fetched_at, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                creative.creative_id,
                creative.advertiser_id,
                creative.advertiser_name,
                creative.format_type,
                creative.domain,
                first_shown,
                last_shown,
                creative.region_count,
                creative.transparency_url,
                creative.domain_url,
                fetched_at,
                source,
            ),
        )
        count += 1
    conn.commit()
    return count


def save_advertisers(conn: sqlite3.Connection, advertisers: list, source: str = '') -> int:
    fetched_at = datetime.now(timezone.utc).isoformat()
    count = 0
    for advertiser in advertisers:
        platform_names = ','.join(advertiser.platform_names)
        conn.execute(
            """
            INSERT OR REPLACE INTO advertisers (
                advertiser_id, name, country_code, platform_names,
                transparency_url, fetched_at, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                advertiser.advertiser_id,
                advertiser.name,
                advertiser.country_code,
                platform_names,
                advertiser.transparency_url,
                fetched_at,
                source,
            ),
        )
        count += 1
    conn.commit()
    return count


def query_creatives(
    conn: sqlite3.Connection,
    *,
    advertiser_id: str | None = None,
    domain: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    conditions = []
    params: list[Any] = []
    if advertiser_id is not None:
        conditions.append('advertiser_id = ?')
        params.append(advertiser_id)
    if domain is not None:
        conditions.append('domain = ?')
        params.append(domain)
    where = 'WHERE ' + ' AND '.join(conditions) if conditions else ''
    rows = conn.execute(
        f'SELECT * FROM creatives {where} ORDER BY fetched_at DESC LIMIT ?',
        (*params, limit),
    )
    return [dict(row) for row in rows]


def query_advertisers(conn: sqlite3.Connection, *, limit: int = 100) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT * FROM advertisers ORDER BY fetched_at DESC LIMIT ?',
        (limit,),
    )
    return [dict(row) for row in rows]


def db_stats(conn: sqlite3.Connection) -> dict[str, int]:
    creatives = conn.execute('SELECT COUNT(*) FROM creatives').fetchone()[0]
    advertisers = conn.execute('SELECT COUNT(*) FROM advertisers').fetchone()[0]
    return {'creatives': creatives, 'advertisers': advertisers}
