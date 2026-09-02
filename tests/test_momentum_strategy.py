from datetime import UTC, datetime
from decimal import Decimal

from packages.core.enums import SignalDirection, Timeframe
from packages.core.models import MarketState
from packages.strategy.momentum import MomentumStrategy

NOW = datetime.now(UTC)


def make_market_state(
    *,
    trend_score: float = 0.80,
    momentum_score: float = 0.75,
    is_tradeable: bool = True,
) -> MarketState:
    return MarketState(
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        timestamp=NOW,
        price=Decimal(3350),
        trend_score=trend_score,
        momentum_score=momentum_score,
        volatility_score=0.50,
        volatility=Decimal(5),
        spread=Decimal("0.20"),
        is_tradeable=is_tradeable,
    )


def test_momentum_strategy_generates_short_signal() -> None:
    strategy = MomentumStrategy()

    signal = strategy.generate_signal(make_market_state())

    assert signal is not None
    assert signal.symbol == "XAUUSD"
    assert signal.direction is SignalDirection.SHORT
    assert signal.entry_price == Decimal(3350)
    assert signal.stop_loss == Decimal(3355)
    assert signal.take_profit == Decimal(3340)
    assert signal.risk_reward_ratio == 2.0
    assert signal.score == 77


def test_momentum_strategy_returns_none_when_market_is_not_tradeable() -> None:
    strategy = MomentumStrategy()

    signal = strategy.generate_signal(
        make_market_state(is_tradeable=False)
    )

    assert signal is None


def test_momentum_strategy_returns_none_when_momentum_is_too_low() -> None:
    strategy = MomentumStrategy()

    signal = strategy.generate_signal(
        make_market_state(momentum_score=0.60)
    )

    assert signal is None


def test_momentum_strategy_returns_none_when_trend_is_too_low() -> None:
    strategy = MomentumStrategy()

    signal = strategy.generate_signal(
        make_market_state(trend_score=0.60)
    )

    assert signal is None


def test_momentum_strategy_generates_long_signal() -> None:
    strategy = MomentumStrategy()

    signal = strategy.generate_signal(
        make_market_state(
            trend_score=0.80,
            momentum_score=0.85,
        )
    )

    assert signal is not None
    assert signal.direction is SignalDirection.LONG
    assert signal.entry_price == Decimal(3350)
    assert signal.stop_loss == Decimal(3345)
    assert signal.take_profit == Decimal(3360)


def test_momentum_strategy_uses_custom_risk_reward_ratio() -> None:
    strategy = MomentumStrategy(risk_reward_ratio=3.0)

    signal = strategy.generate_signal(
        make_market_state(
            trend_score=0.80,
            momentum_score=0.85,
        )
    )

    assert signal is not None
    assert signal.direction is SignalDirection.LONG
    assert signal.risk_reward_ratio == 3.0
    assert signal.take_profit == Decimal(3365)
