from abc import ABC, abstractmethod

from packages.core.models import MarketState, Order, Signal


class TradingEngine(ABC):
    """Abstract interface for the AtlasTrader trading engine."""

    @abstractmethod
    async def process_market_state(
        self,
        market_state: MarketState,
    ) -> Order | None:
        """Process market state and execute an approved signal."""
        raise NotImplementedError

    @abstractmethod
    async def execute_signal(
        self,
        signal: Signal,
        market_state: MarketState | None = None,
    ) -> Order | None:
        """Validate and execute an approved trading signal."""
        raise NotImplementedError