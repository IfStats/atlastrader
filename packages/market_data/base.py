from abc import ABC, abstractmethod
from datetime import datetime

from packages.core.enums import Timeframe
from packages.core.models import Candle, MarketState, Quote


class MarketDataProvider(ABC):
    """Abstract interface for market-data providers."""

    @abstractmethod
    async def get_quote(self, symbol: str) -> Quote:
        """Fetch the latest quote for a symbol."""
        raise NotImplementedError

    @abstractmethod
    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        """Fetch historical candles for a symbol."""
        raise NotImplementedError

    @abstractmethod
    async def subscribe_quotes(self, symbols: list[str]) -> None:
        """Subscribe to live quote updates."""
        raise NotImplementedError

    @abstractmethod
    async def unsubscribe_quotes(self, symbols: list[str]) -> None:
        """Unsubscribe from live quote updates."""
        raise NotImplementedError

    async def get_market_state(
        self,
        symbol: str,
    ) -> MarketState:
        """Fetch the normalized current market state.

        Providers that expose normalized market-state retrieval can
        override this method. The base implementation remains concrete
        so existing market-data providers are not forced to implement it.
        """
        raise NotImplementedError(
            "This market-data provider does not implement "
            "get_market_state"
        )