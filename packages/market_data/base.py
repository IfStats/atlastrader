from abc import ABC, abstractmethod
from datetime import datetime

from packages.core.enums import Timeframe
from packages.core.models import Candle, Quote


class MarketDataProvider(ABC):
    """Interface for providers that supply market data to AtlasTrader."""

    @abstractmethod
    async def get_quote(self, symbol: str) -> Quote:
        """Return the latest quote for an instrument."""
        raise NotImplementedError

    @abstractmethod
    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        """Return historical candles ordered from oldest to newest."""
        raise NotImplementedError

    @abstractmethod
    async def subscribe_quotes(self, symbols: list[str]) -> None:
        """Start receiving live quotes for the supplied symbols."""
        raise NotImplementedError

    @abstractmethod
    async def unsubscribe_quotes(self, symbols: list[str]) -> None:
        """Stop receiving live quotes."""
        raise NotImplementedError