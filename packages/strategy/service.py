
from packages.core.models import MarketState, Signal
from packages.strategy.interfaces import Strategy


class StrategyService:
    """Coordinates multiple trading strategies."""

    def __init__(
        self,
        strategies: list[Strategy],
    ) -> None:
        if not strategies:
            raise ValueError("At least one strategy is required")

        self.strategies = strategies

    def generate_signals(
        self,
        market_state: MarketState,
    ) -> list[Signal]:
        """Generate all valid signals for the current market state."""

        signals: list[Signal] = []

        for strategy in self.strategies:
            signal = strategy.generate_signal(market_state)

            if signal is not None:
                signals.append(signal)

        return signals

    def select_signal(
        self,
        market_state: MarketState,
    ) -> Signal | None:
        """Select the highest-scoring signal from all strategies."""

        signals = self.generate_signals(market_state)

        if not signals:
            return None

        return max(
            signals,
            key=lambda signal: signal.score,
        )

