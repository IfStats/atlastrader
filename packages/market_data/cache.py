from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TypeVar

from packages.core.enums import Timeframe
from packages.core.models import Candle, Quote

T = TypeVar("T")


@dataclass(slots=True)
class CacheEntry[T]:
    value: T
    expires_at: datetime


class MarketDataCache:
    """In-memory TTL cache for market-data objects."""

    def __init__(
        self,
        *,
        quote_ttl: timedelta = timedelta(seconds=2),
        candle_ttl: timedelta = timedelta(seconds=30),
        quote_max_age: timedelta = timedelta(seconds=5),
    ) -> None:
        if quote_ttl <= timedelta(0):
            raise ValueError("quote_ttl must be greater than zero")

        if candle_ttl <= timedelta(0):
            raise ValueError("candle_ttl must be greater than zero")

        if quote_max_age <= timedelta(0):
            raise ValueError("quote_max_age must be greater than zero")

        self.quote_ttl = quote_ttl
        self.candle_ttl = candle_ttl
        self.quote_max_age = quote_max_age

        self._quotes: dict[str, CacheEntry[Quote]] = {}
        self._candles: dict[
            tuple[str, Timeframe, datetime, datetime],
            CacheEntry[list[Candle]],
        ] = {}

    @staticmethod
    def _now() -> datetime:
        return datetime.now().astimezone()

    def set_quote(self, quote: Quote) -> None:
        """Store the latest quote for a symbol."""

        self._quotes[quote.symbol] = CacheEntry(
            value=quote,
            expires_at=self._now() + self.quote_ttl,
        )

    def get_quote(self, symbol: str) -> Quote | None:
        """Return a cached quote if it has not expired or gone stale."""

        entry = self._quotes.get(symbol)

        if entry is None:
            return None

        now = self._now()

        if now >= entry.expires_at:
            del self._quotes[symbol]
            return None

        quote_age = now - entry.value.timestamp

        if quote_age > self.quote_max_age:
            del self._quotes[symbol]
            return None

        return entry.value

    def set_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        candles: list[Candle],
    ) -> None:
        """Store historical candles for a specific query window."""

        key = (symbol, timeframe, start, end)

        self._candles[key] = CacheEntry(
            value=candles,
            expires_at=self._now() + self.candle_ttl,
        )

    def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle] | None:
        """Return cached candles if they have not expired."""

        key = (symbol, timeframe, start, end)
        entry = self._candles.get(key)

        if entry is None:
            return None

        if self._now() >= entry.expires_at:
            del self._candles[key]
            return None

        return entry.value

    def clear(self) -> None:
        """Clear all cached market data."""

        self._quotes.clear()
        self._candles.clear()

    def clear_symbol(self, symbol: str) -> None:
        """Clear all cached data associated with a symbol."""

        self._quotes.pop(symbol, None)

        keys_to_remove = [
            key
            for key in self._candles
            if key[0] == symbol
        ]

        for key in keys_to_remove:
            del self._candles[key]