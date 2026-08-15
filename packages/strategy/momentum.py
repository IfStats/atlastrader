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
        self.minimum_score = minimum_score
        self.risk_reward_ratio = risk_reward_ratio

    def generate_signal(self, market_state: MarketState) -> Signal | None:
        if not market_state.is_tradeable:
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

        if direction is SignalDirection.LONG:
            stop_loss = entry_price - risk_distance
            take_profit = entry_price + (
                risk_distance * Decimal(str(self.risk_reward_ratio))
            )
        else:
            stop_loss = entry_price + risk_distance
            take_profit = entry_price - (
                risk_distance * Decimal(str(self.risk_reward_ratio))
            )

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