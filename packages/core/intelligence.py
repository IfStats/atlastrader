from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MarketNews(BaseModel):
    id: str
    headline: str
    source: str
    published_at: datetime
    url: str | None = None
    summary: str | None = None

    # Provider provenance.
    provider: str | None = None
    external_id: str | None = None

    symbols: list[str] = Field(default_factory=list)
    asset_classes: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)

    sentiment_score: float = Field(default=0, ge=-1, le=1)
    relevance_score: float = Field(default=0, ge=0, le=1)
    impact_score: float = Field(default=0, ge=0, le=1)
    event_type: str | None = None


class MarketEvent(BaseModel):
    id: str
    name: str
    event_type: str
    scheduled_at: datetime
    source: str

    # Provider provenance.
    provider: str | None = None
    external_id: str | None = None

    symbols: list[str] = Field(default_factory=list)
    asset_classes: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)

    expected_value: Decimal | None = None
    previous_value: Decimal | None = None
    actual_value: Decimal | None = None

    importance: float = Field(default=0, ge=0, le=1)
    is_confirmed: bool = False
    description: str | None = None