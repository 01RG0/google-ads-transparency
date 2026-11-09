"""Typed views over the Transparency Center's numeric-key RPC JSON."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RPCModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Advertiser(RPCModel):
    advertiser_id: str = Field(alias="1")
    name: str | None = Field(default=None, alias="2")
    country_code: str | None = Field(default=None, alias="3")


class AdvertiserSuggestion(RPCModel):
    name: str | None = Field(default=None, alias="1")
    advertiser_id: str | None = Field(default=None, alias="2")
    country_code: str | None = Field(default=None, alias="3")
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)


class Timestamp(RPCModel):
    seconds: str | None = Field(default=None, alias="1")
    nanos: int = Field(default=0, alias="2")


class Creative(RPCModel):
    advertiser_id: str = Field(alias="1")
    creative_id: str = Field(alias="2")
    content: dict[str, Any] | None = Field(default=None, alias="3")
    format_type: int | None = Field(default=None, alias="4")
    first_shown: Timestamp | None = Field(default=None, alias="6")
    last_shown: Timestamp | None = Field(default=None, alias="7")
    advertiser_name: str | None = Field(default=None, alias="12")
    region_count: int | None = Field(default=None, alias="13")
    domain: str | None = Field(default=None, alias="14")


class CreativePage(RPCModel):
    creatives: list[Creative] = Field(default_factory=list, alias="1")
    next_cursor: str | None = Field(default=None, alias="2")
    total_count: str | None = Field(default=None, alias="4")
    alternate_count: str | None = Field(default=None, alias="5")


class CreativeVariationContent(RPCModel):
    preview_url: str | None = Field(default=None, alias="4")


class CreativeVariation(RPCModel):
    content: CreativeVariationContent | None = Field(default=None, alias="1")


class CreativeRegion(RPCModel):
    geo_id: int | None = Field(default=None, alias="1")
    last_shown_date: int | None = Field(default=None, alias="5")


class CreativeDetail(RPCModel):
    advertiser_id: str = Field(alias="1")
    creative_id: str = Field(alias="2")
    last_shown: Timestamp | None = Field(default=None, alias="4")
    variations: list[CreativeVariation] = Field(default_factory=list, alias="5")
    format_type: int | None = Field(default=None, alias="8")
    regions: list[CreativeRegion] = Field(default_factory=list, alias="17")
    advertiser: dict[str, Any] | None = Field(default=None, alias="22")


class CreativeSearchRequest(BaseModel):
    advertiser_id: str | None = None
    domain: str | None = None
    region: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    cursor: str | None = None
    page_size: int = 40


class DunsMappingEntry(RPCModel):
    advertiser_id: str = Field(alias="1")
    duns_number: str = Field(alias="2")
