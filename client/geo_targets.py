"""Country-level Google Ads geo targets used by the Transparency Center filter.

Data source and attribution are recorded in geo_targets_countries.json.
"""
from __future__ import annotations

import json
from pathlib import Path


_DATA = json.loads(Path(__file__).with_name("geo_targets_countries.json").read_text(encoding="utf-8"))
COUNTRY_GEO_TARGET_IDS: dict[str, int] = {
    row["code"].upper(): int(row["geo_target_id"])
    for row in _DATA["countries"]
}
# The current Google Ads CSV omits Palestine, but the Transparency Center
# region selector directly emitted geo ID 2275 for Palestine.
COUNTRY_GEO_TARGET_IDS["PS"] = 2275
_names: dict[str, list[str]] = {}
for _row in _DATA["countries"]:
    _names.setdefault(_row["name"].casefold(), []).append(_row["code"].upper())
COUNTRY_NAME_TO_CODE: dict[str, str] = {
    name: codes[0] for name, codes in _names.items() if len(codes) == 1
}
COUNTRY_NAME_TO_CODE["palestine"] = "PS"


def lookup_country_geo_target(region: str) -> int | None:
    """Resolve a country/territory name or ISO alpha-2 code; None means anywhere."""
    normalized = region.strip()
    if not normalized or normalized.casefold() in {"anywhere", "all", "worldwide"}:
        return None
    code = normalized.upper()
    if code in COUNTRY_GEO_TARGET_IDS:
        return COUNTRY_GEO_TARGET_IDS[code]
    code = COUNTRY_NAME_TO_CODE.get(normalized.casefold())
    if code is not None:
        return COUNTRY_GEO_TARGET_IDS[code]
    return None


SUPPORTED_REGIONS: list[str] = sorted(
    set(COUNTRY_GEO_TARGET_IDS.keys()) |
    {name.title() for name in COUNTRY_NAME_TO_CODE.keys()}
)


def list_regions() -> list[str]:
    return SUPPORTED_REGIONS
