from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.core.enums import (
    SignalDirection,
    StrategyType,
    Timeframe,
)
from packages.core.models import MarketState
from packages.strategy.breakout import BreakoutStrategy

NOW = datetime.now(UTC)


def make_market_state(
    *,
    price: Decimal = Decimal("3352"),
    range_high: Decimal | None = Decimal("3350"),
    range_low: Decimal | None = Decimal("3335"),
    is_tradeable: bool = True,
) -> MarketState:
    return MarketState(
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        timestamp=NOW,
        price=price,
        trend_score=0.80,
        momentum_score=0.82,
        volatility_score=0.60,
        volatility=Decimal("5"),
        spread=Decimal("0.20"),
        range_high=range_high,
        range_low=range_low,
        is_tradeable=is_tradeable,
    )


def test_breakout_strategy_generates_long_above_range_high() -> None:
    strategy = BreakoutStrategy()

    signal = strategy.generate_signal(
        make_market_state()
    )

    assert signal is not None
    assert signal.symbol == "XAUUSD"
    assert signal.strategy is StrategyType.BREAKOUT
    assert signal.direction is SignalDirection.LONG
    assert signal.entry_price == Decimal("3352")
    assert signal.stop_loss == Decimal("3347")
    assert signal.take_profit == Decimal("3362")
    assert signal.risk_reward_ratio == 2.0


def test_breakout_strategy_generates_short_below_range_low() -> None:
    strategy = BreakoutStrategy()

    state = make_market_state(
        price=Decimal("3332"),
    )
    state.trend_score = -0.80
    state.momentum_score = -0.82

    signal = strategy.generate_signal(state)

    assert signal is not None
    assert signal.symbol == "XAUUSD"
    assert signal.strategy is StrategyType.BREAKOUT
    assert signal.direction is SignalDirection.SHORT
    assert signal.entry_price == Decimal("3332")
    assert signal.stop_loss == Decimal("3337")
    assert signal.take_profit == Decimal("3322")
    assert signal.risk_reward_ratio == 2.0


def test_breakout_strategy_returns_none_inside_range() -> None:
    strategy = BreakoutStrategy()

    signal = strategy.generate_signal(
        make_market_state(
            price=Decimal("3342"),
        )
    )

    assert signal is None


def test_breakout_strategy_returns_none_at_range_boundaries() -> None:
    strategy = BreakoutStrategy()

    at_range_high = strategy.generate_signal(
        make_market_state(
            price=Decimal("3350"),
        )
    )

    at_range_low = strategy.generate_signal(
        make_market_state(
            price=Decimal("3335"),
        )
    )

    assert at_range_high is None
    assert at_range_low is None


def test_breakout_strategy_returns_none_when_market_is_not_tradeable() -> None:
    strategy = BreakoutStrategy()

    signal = strategy.generate_signal(
        make_market_state(
            is_tradeable=False,
        )
    )

    assert signal is None


def test_breakout_strategy_returns_none_without_breakout_range() -> None:
    strategy = BreakoutStrategy()

    signal = strategy.generate_signal(
        make_market_state(
            range_high=None,
            range_low=None,
        )
    )

    assert signal is None


def test_breakout_strategy_returns_none_when_volatility_is_zero() -> None:
    strategy = BreakoutStrategy()

    state = make_market_state()
    state.volatility = Decimal("0")

    signal = strategy.generate_signal(state)

    assert signal is None


def test_breakout_strategy_uses_custom_risk_reward_ratio() -> None:
    strategy = BreakoutStrategy(
        risk_reward_ratio=3.0,
    )

    signal = strategy.generate_signal(
        make_market_state()
    )

    assert signal is not None
    assert signal.direction is SignalDirection.LONG
    assert signal.risk_reward_ratio == 3.0
    assert signal.stop_loss == Decimal("3347")
    assert signal.take_profit == Decimal("3367")


@pytest.mark.parametrize(
    "risk_reward_ratio",
    [0.0, -1.0],
)
def test_breakout_strategy_rejects_invalid_risk_reward_ratio(
    risk_reward_ratio: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="risk_reward_ratio must be greater than zero",
    ):
        BreakoutStrategy(
            risk_reward_ratio=risk_reward_ratio,
        )


def test_breakout_strategy_rejects_weak_breakout_when_threshold_is_configured() -> None:
    strategy = BreakoutStrategy(
        minimum_breakout_ratio=Decimal("0.25"),
    )

    signal = strategy.generate_signal(
        make_market_state(
            price=Decimal("3350.50"),
        )
    )

    assert signal is None


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


def test_breakout_strategy_rejects_bearish_breakout_with_bullish_confirmation() -> None:
    strategy = BreakoutStrategy()

    state = make_market_state(
        price=Decimal("3332"),
    )

    state.trend_score = 0.80
    state.momentum_score = 0.75

    signal = strategy.generate_signal(state)

    assert signal is None