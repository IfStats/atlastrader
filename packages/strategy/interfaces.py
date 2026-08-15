from abc import ABC, abstractmethod

from packages.core.models import MarketState, Signal


class Strategy(ABC):
    """Abstract interface for generating trading signals."""

    @abstractmethod
    def generate_signal(self, market_state: MarketState) -> Signal | None:
        """Generate a trading signal from the current market state."""
        raise NotImplementedError