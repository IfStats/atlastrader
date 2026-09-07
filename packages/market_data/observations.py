from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from packages.core.enums import Timeframe
from packages.core.models import Candle


class PriceObservationType(StrEnum):
    """Classification of a non-execution market price."""

    MID = "mid"
    LAST = "last"
    INDICATIVE = "indicative"


class MarketPriceObservation(BaseModel):
    """A normalized market price observed from a reference data source."""

    symbol: str
    price: Decimal = Field(gt=0)
    timestamp: datetime
    source: str
    price_type: PriceObservationType

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        """Normalize and validate the canonical instrument symbol."""
        normalized = value.strip().upper()

        if not normalized:
            raise ValueError("symbol must not be empty")

        return normalized

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        """Normalize and validate the provider source name."""
        normalized = value.strip()

        if not normalized:
            raise ValueError("source must not be empty")

        return normalized

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        """Require timezone-aware timestamps and normalize them to UTC."""
        if value.tzinfo is None:
            raise ValueError(
                "timestamp must be timezone-aware"
            )

        return value.astimezone(UTC)


class ObservationalMarketDataProvider(ABC):
    """Interface for non-execution market-data reference providers."""

    @abstractmethod
    async def connect(self) -> None:
        """Connect to the reference market-data provider."""
        raise NotImplementedError

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the reference market-data provider."""
        raise NotImplementedError

    @abstractmethod
    async def get_observation(
        self,
        symbol: str,
    ) -> MarketPriceObservation:
        """Return the latest normalized reference-price observation."""
        raise NotImplementedError

    @abstractmethod
    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        """Return historical observational candles."""
        raise NotImplementedError