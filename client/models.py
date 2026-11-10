"""Typed views over the Transparency Center's numeric-key RPC JSON."""
from __future__ import annotations
from datetime import datetime, timezone

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class RPCModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    def __repr__(self) -> str:
        parts = []
        for name, field_info in self.model_fields.items():
            if field_info.exclude:
                continue
            val = getattr(self, name, None)
            if val is not None:
                parts.append(f"{name}={val!r}")
        return f"{self.__class__.__name__}({', '.join(parts)})"


class Advertiser(RPCModel):
    advertiser_id: str = Field(alias="1", description="Unique advertiser ID starting with AR")
    name: str | None = Field(default=None, alias="2", description="Advertiser display name")
    country_code: str | None = Field(default=None, alias="3", description="ISO 3166-1 alpha-2 country code")

    @computed_field
    @property
    def transparency_url(self) -> str | None:
        if self.advertiser_id:
            return f'https://adstransparency.google.com/?region=anywhere&advertiser={self.advertiser_id}'
        return None


class AdvertiserSuggestion(RPCModel):
    name: str | None = Field(default=None, alias="1")
    advertiser_id: str | None = Field(default=None, alias="2", description="Unique advertiser ID starting with AR")
    country_code: str | None = Field(default=None, alias="3")
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @computed_field
    @property
    def transparency_url(self) -> str | None:
        if self.advertiser_id:
            return f'https://adstransparency.google.com/?region=anywhere&advertiser={self.advertiser_id}'
        return None
    ad_count_lower: str | None = Field(default=None, exclude=True)
    ad_count_upper: str | None = Field(default=None, exclude=True)

    @model_validator(mode="before")
    @classmethod
    def _populate_ad_counts(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        raw = values.get("raw")
        if not isinstance(raw, dict):
            raw = values
        ad_counts = raw.get("4")
        if isinstance(ad_counts, dict):
            ad_counts = ad_counts.get("2")
        if isinstance(ad_counts, dict):
            if "ad_count_lower" not in values:
                values["ad_count_lower"] = ad_counts.get("1")
            if "ad_count_upper" not in values:
                values["ad_count_upper"] = ad_counts.get("2")
        return values


class Timestamp(RPCModel):
    seconds: str | None = Field(default=None, alias="1")
    nanos: int = Field(default=0, alias="2")

    def to_datetime(self) -> datetime | None:
        if self.seconds is None:
            return None
        ts = int(self.seconds) + self.nanos / 1_000_000_000
        return datetime.fromtimestamp(ts, tz=timezone.utc)


class Creative(RPCModel):
    advertiser_id: str = Field(alias="1", description="Advertiser that owns this creative")
    creative_id: str = Field(alias="2", description="Unique creative ID starting with CR")
    content: dict[str, Any] | None = Field(default=None, alias="3")
    format_type: int | None = Field(default=None, alias="4", description="Ad format: 1=Display, 2=Video, 3=Text/Search")
    first_shown: Timestamp | None = Field(default=None, alias="6")
    last_shown: Timestamp | None = Field(default=None, alias="7")
    advertiser_name: str | None = Field(default=None, alias="12")
    region_count: int | None = Field(default=None, alias="13")
    domain: str | None = Field(default=None, alias="14", description="Advertiser domain")

    @computed_field
    @property
    def transparency_url(self) -> str | None:
        if self.advertiser_id:
            return f'https://adstransparency.google.com/?region=anywhere&advertiser={self.advertiser_id}'
        return None

    @computed_field
    @property
    def domain_url(self) -> str | None:
        if self.domain:
            return f'https://{self.domain}'
        return None


class CreativePage(RPCModel):
    creatives: list[Creative] = Field(default_factory=list, alias="1")
    next_cursor: str | None = Field(default=None, alias="2", description="Pagination cursor; pass as cursor= in the next call")
    total_count: str | None = Field(default=None, alias="4", description="Approximate total result count (string)")
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
    creative_id: str = Field(alias="2", description="Unique creative ID starting with CR")
    last_shown: Timestamp | None = Field(default=None, alias="4")
    variations: list[CreativeVariation] = Field(default_factory=list, alias="5")
    format_type: int | None = Field(default=None, alias="8")
    regions: list[CreativeRegion] = Field(default_factory=list, alias="17")
    advertiser: dict[str, Any] | None = Field(default=None, alias="22")

    @computed_field
    @property
    def transparency_url(self) -> str | None:
        if self.advertiser_id:
            return f'https://adstransparency.google.com/?region=anywhere&advertiser={self.advertiser_id}'
        return None

    @computed_field
    @property
    def preview_url(self) -> str | None:
        try:
            return self.variations[0].content.preview_url
        except (IndexError, AttributeError):
            return None


class CreativeSearchRequest(BaseModel):
    advertiser_id: str | None = None
    domain: str | None = None
    region: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    cursor: str | None = None
    page_size: int = 40


class DunsMappingEntry(RPCModel):
    advertiser_id: str = Field(alias="1", description="Unique advertiser ID starting with AR")
    duns_number: str = Field(alias="2", description="9-digit DUNS number as a string")
