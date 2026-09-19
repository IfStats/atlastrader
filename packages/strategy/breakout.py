from datetime import UTC, datetime
from decimal import Decimal

from packages.core.enums import SignalDirection, StrategyType
from packages.core.models import MarketState, Signal
from packages.strategy.interfaces import Strategy


class BreakoutStrategy(Strategy):
    """Generate signals when price breaks a prior trading range."""

    def __init__(
        self,
        *,
        risk_reward_ratio: float = 2.0,
        minimum_breakout_ratio: Decimal = Decimal("0"),
    ) -> None:
        if risk_reward_ratio <= 0:
            raise ValueError(
                "risk_reward_ratio must be greater than zero"
            )

        if minimum_breakout_ratio < Decimal("0"):
            raise ValueError(
                "minimum_breakout_ratio must be non-negative"
            )

        self.risk_reward_ratio = risk_reward_ratio
        self.minimum_breakout_ratio = minimum_breakout_ratio

    def generate_signal(
        self,
        market_state: MarketState,
    ) -> Signal | None:
        """Generate a signal from a confirmed structural breakout."""

        if not market_state.is_tradeable:
            return None

        if market_state.volatility <= Decimal(0):
            return None

        if (
            market_state.range_high is None
            or market_state.range_low is None
        ):
            return None

        entry_price = market_state.price

        if entry_price > market_state.range_high:
            direction = SignalDirection.LONG
            breakout_distance = (
                entry_price - market_state.range_high
            )
        elif entry_price < market_state.range_low:
            direction = SignalDirection.SHORT
            breakout_distance = (
                market_state.range_low - entry_price
            )
        else:
            return None

        if (
            direction is SignalDirection.LONG
            and market_state.trend_score < 0
            and market_state.momentum_score < 0
):
          return None

        if (
            direction is SignalDirection.SHORT
             and market_state.trend_score > 0
             and market_state.momentum_score > 0
):
         return None

        breakout_ratio = (
            breakout_distance / market_state.volatility
        )

        if breakout_ratio < self.minimum_breakout_ratio:
            return None

        risk_distance = market_state.volatility
        reward_distance = (
            risk_distance
            * Decimal(str(self.risk_reward_ratio))
        )

        if direction is SignalDirection.LONG:
            stop_loss = entry_price - risk_distance
            take_profit = entry_price + reward_distance
        else:
            stop_loss = entry_price + risk_distance
            take_profit = entry_price - reward_distance

        breakout_strength = min(
            breakout_distance / risk_distance,
            Decimal(1),
        )

        signal_score = float(
            Decimal(50)
            + breakout_strength * Decimal(50)
        )

        return Signal(
            symbol=market_state.symbol,
            direction=direction,
            strategy=StrategyType.BREAKOUT,
            score=signal_score,
            timestamp=datetime.now(UTC),
            timeframe=market_state.timeframe,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=self.risk_reward_ratio,
            rationale=[
                "Price breached prior trading range",
                "Breakout range derived from prior candles",
                "Market is tradeable",
            ],
        )

def test_breakout_strategy_rejects_negative_minimum_breakout_ratio() -> None:
    with pytest.raises(
        ValueError,
        match="minimum_breakout_ratio must be non-negative",
    ):
        BreakoutStrategy(
            minimum_breakout_ratio=Decimal("-0.01"),
        )

def test_breakout_strategy_rejects_negative_minimum_breakout_ratio() -> None:
    with pytest.raises(
        ValueError,
        match="minimum_breakout_ratio must be non-negative",
    ):
        BreakoutStrategy(
            minimum_breakout_ratio=Decimal("-0.01"),
        )

def test_breakout_strategy_rejects_bullish_breakout_with_bearish_confirmation() -> None:
    strategy = BreakoutStrategy()

    state = make_market_state(
        price=Decimal("3352"),
    )

    state.trend_score = -0.80
    state.momentum_score = -0.75

    signal = strategy.generate_signal(state)

    assert signal is None        
                