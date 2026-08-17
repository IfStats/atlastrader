
from datetime import UTC, datetime
from decimal import Decimal

from packages.core.enums import SignalDirection, StrategyType
from packages.core.models import MarketState, Signal
from packages.strategy.interfaces import Strategy


class MomentumStrategy(Strategy):
    """Deterministic momentum strategy for development and testing."""

    def __init__(
        self,
        *,
        minimum_score: Decimal = Decimal("0.70"),
        risk_reward_ratio: float = 2.0,
    ) -> None:
        if minimum_score < Decimal(0):
            raise ValueError("minimum_score must be non-negative")

        if minimum_score > Decimal(1):
            raise ValueError("minimum_score must not exceed 1")

        if risk_reward_ratio <= 0:
            raise ValueError("risk_reward_ratio must be greater than zero")

        self.minimum_score = minimum_score
        self.risk_reward_ratio = risk_reward_ratio

    def generate_signal(self, market_state: MarketState) -> Signal | None:
        """Generate a momentum signal from the current market state."""

        if not market_state.is_tradeable:
            return None

        if market_state.price <= Decimal(0):
            return None

        if market_state.volatility <= Decimal(0):
            return None

        momentum_score = Decimal(str(market_state.momentum_score))
        trend_score = Decimal(str(market_state.trend_score))

        if momentum_score < self.minimum_score:
            return None

        if trend_score < self.minimum_score:
            return None

        if momentum_score >= trend_score:
            direction = SignalDirection.LONG
        else:
            direction = SignalDirection.SHORT

        entry_price = market_state.price
        risk_distance = market_state.volatility
        reward_distance = (
            risk_distance * Decimal(str(self.risk_reward_ratio))
        )

        if direction is SignalDirection.LONG:
            stop_loss = entry_price - risk_distance
            take_profit = entry_price + reward_distance
        else:
            stop_loss = entry_price + risk_distance
            take_profit = entry_price - reward_distance

        if direction is SignalDirection.LONG:
            if not stop_loss < entry_price < take_profit:
                return None
        else:
            if not take_profit < entry_price < stop_loss:
                return None

        signal_score = int(
            (trend_score + momentum_score) * Decimal(50)
        )

        return Signal(
            symbol=market_state.symbol,
            direction=direction,
            strategy=StrategyType.MOMENTUM,
            score=signal_score,
            timestamp=datetime.now(UTC),
            timeframe=market_state.timeframe,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=self.risk_reward_ratio,
            rationale=[
                "Momentum threshold satisfied",
                "Trend alignment confirmed",
                "Market is tradeable",
            ],
        )

