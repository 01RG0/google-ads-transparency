"""Small FastAPI facade over the async client."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from client import TransparencyClient
from client.errors import ResponseShapeError, UnsupportedFilterError, UpstreamHTTPError
from client.models import CreativeSearchRequest, DunsMappingEntry
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.ads_client = TransparencyClient()
    yield
    await app.state.ads_client.close()


app = FastAPI(
    title="Ads Transparency API",
    version="0.1.0",
    description="REST API for the Google Ads Transparency Center. All endpoints are public and require no authentication.",
    lifespan=lifespan,
)


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, UnsupportedFilterError):
        return HTTPException(status_code=501, detail=str(exc))
    if isinstance(exc, UpstreamHTTPError):
        return HTTPException(status_code=502, detail=str(exc))
    if isinstance(exc, ResponseShapeError):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=502, detail="Transparency Center request failed")


@app.get("/advertisers/search", responses={502: {"model": ErrorResponse}})
async def search_advertisers(
    q: str = Query(min_length=1, description="Advertiser name or partial name to search"),
    limit: int = Query(10, ge=1, le=40, description="Maximum number of results (1-40)"),
):
    try:
        return await app.state.ads_client.search_advertisers(q, limit=limit)
    except Exception as exc:
        raise _translate(exc) from exc


@app.get(
    "/domains/{domain}/creatives",
    responses={502: {"model": ErrorResponse}},
)
async def search_domain(
    domain: str,
    cursor: str | None = Query(None, description="Pagination cursor from a previous response"),
    page_size: int = Query(40, ge=1, le=40, description="Number of results per page (1-40)"),
):
    try:
        return await app.state.ads_client.search_by_domain(domain, cursor=cursor, page_size=page_size)
    except Exception as exc:
        raise _translate(exc) from exc


@app.post("/creatives/search", responses={502: {"model": ErrorResponse}})
async def list_creatives(request: CreativeSearchRequest):
    try:
        return await app.state.ads_client.list_creatives(**request.model_dump())
    except Exception as exc:
        raise _translate(exc) from exc


@app.get(
    "/advertisers/{advertiser_id}",
    responses={404: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def get_advertiser(advertiser_id: str):
    try:
        result = await app.state.ads_client.get_advertiser(advertiser_id)
    except Exception as exc:
        raise _translate(exc) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Advertiser not found")
    return result


@app.get(
    "/advertisers/{advertiser_id}/creatives/{creative_id}",
    responses={404: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def get_creative(advertiser_id: str, creative_id: str):
    try:
        result = await app.state.ads_client.get_creative(advertiser_id, creative_id)
    except Exception as exc:
        raise _translate(exc) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Creative not found")
    return result


@app.get('/duns-mapping', responses={502: {'model': ErrorResponse}})
async def get_duns_mapping():
    '''Returns the full advertiser->DUNS mapping (6000+ entries). Cache this response client-side.'''
    try:
        return await app.state.ads_client.get_advertiser_duns_mapping()
    except Exception as exc:
        raise _translate(exc) from exc


@app.get(
    '/advertisers/{advertiser_id}/stats',
    responses={404: {'model': ErrorResponse}, 502: {'model': ErrorResponse}},
)
async def get_advertiser_stats(
    advertiser_id: str,
    pages: int = Query(3, ge=1, le=20, description='Pages of creatives to sample (1-20, default 3)'),
):
    '''Sample an advertiser creative pages and return format breakdown, top domains, date range, and trend.'''
    import collections
    adv = await app.state.ads_client.get_advertiser(advertiser_id)
    if adv is None:
        raise HTTPException(status_code=404, detail='Advertiser not found')
    
    format_counts: dict[int, int] = {}
    domains: dict[str, int] = {}
    monthly: dict[str, int] = {}
    earliest = None
    latest = None
    total_count = None
    sampled = 0
    region_total = 0
    region_items = 0
    cursor = None
    
    for _ in range(pages):
        try:
            page = await app.state.ads_client.list_creatives(advertiser_id=advertiser_id, cursor=cursor)
        except Exception as exc:
            raise _translate(exc) from exc
        if total_count is None:
            total_count = page.total_count
        for c in page.creatives:
            sampled += 1
            ft = c.format_type or 0
            format_counts[ft] = format_counts.get(ft, 0) + 1
            if c.domain:
                domains[c.domain] = domains.get(c.domain, 0) + 1
            if c.region_count is not None:
                region_total += c.region_count
                region_items += 1
            if c.last_shown and c.last_shown.seconds:
                dt = c.last_shown.to_datetime()
                if dt:
                    key = dt.strftime('%Y-%m')
                    monthly[key] = monthly.get(key, 0) + 1
                    if latest is None or dt > latest:
                        latest = dt
            if c.first_shown and c.first_shown.seconds:
                dt = c.first_shown.to_datetime()
                if dt and (earliest is None or dt < earliest):
                    earliest = dt
        if not page.next_cursor:
            break
        cursor = page.next_cursor
    
    FORMAT_NAMES = {1: 'Display', 2: 'Video', 3: 'Search', 0: 'Unknown'}
    sorted_months = sorted(monthly)
    if len(sorted_months) >= 6:
        third = max(1, len(sorted_months) // 3)
        early = sum(monthly[m] for m in sorted_months[:third]) / third
        late = sum(monthly[m] for m in sorted_months[-third:]) / third
        trend = 'increasing' if late > early * 1.2 else 'decreasing' if late < early * 0.8 else 'stable'
    else:
        trend = 'unknown'
    
    return {
        'advertiser_id': adv.advertiser_id,
        'name': adv.name,
        'country_code': adv.country_code,
        'total_count': total_count,
        'sampled': sampled,
        'pages_fetched': pages,
        'format_breakdown': {FORMAT_NAMES.get(k, 'Unknown'): v for k, v in format_counts.items() if v},
        'top_domains': dict(sorted(domains.items(), key=lambda x: -x[1])[:10]),
        'avg_region_count': round(region_total / region_items, 1) if region_items else None,
        'earliest_first_shown': earliest.isoformat() if earliest else None,
        'latest_last_shown': latest.isoformat() if latest else None,
        'activity_trend': trend,
        'peak_months': sorted(monthly, key=lambda m: -monthly[m])[:3],
    }
