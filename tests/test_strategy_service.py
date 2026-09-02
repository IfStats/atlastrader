
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.core.enums import SignalDirection, StrategyType, Timeframe
from packages.core.models import MarketState, Signal
from packages.strategy.interfaces import Strategy
from packages.strategy.momentum import MomentumStrategy
from packages.strategy.service import StrategyService

NOW = datetime.now(UTC)


def make_market_state(
    *,
    trend_score: float = 0.80,
    momentum_score: float = 0.80,
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


class StaticStrategy(Strategy):
    """Deterministic strategy used to test orchestration."""

    def __init__(
        self,
        signal: Signal | None,
    ) -> None:
        self.signal = signal

    def generate_signal(
        self,
        market_state: MarketState,
    ) -> Signal | None:
        return self.signal


def make_signal(
    *,
    score: int,
) -> Signal:
    return Signal(
        symbol="XAUUSD",
        direction=SignalDirection.LONG,
        strategy=StrategyType.MOMENTUM,
        score=score,
        timestamp=NOW,
        timeframe=Timeframe.M5,
        entry_price=Decimal(3350),
        stop_loss=Decimal(3345),
        take_profit=Decimal(3360),
        risk_reward_ratio=2.0,
        rationale=["test signal"],
    )


def test_strategy_service_requires_at_least_one_strategy() -> None:
    with pytest.raises(
        ValueError,
        match="At least one strategy is required",
    ):
        StrategyService([])


def test_strategy_service_collects_signals() -> None:
    first = make_signal(score=70)
    second = make_signal(score=80)

    service = StrategyService(
        [
            StaticStrategy(first),
            StaticStrategy(None),
            StaticStrategy(second),
        ]
    )

    signals = service.generate_signals(
        make_market_state()
    )

    assert signals == [first, second]


def test_strategy_service_returns_empty_when_no_strategy_generates_signal() -> None:
    service = StrategyService(
        [
            StaticStrategy(None),
            StaticStrategy(None),
        ]
    )

    signals = service.generate_signals(
        make_market_state()
    )

    assert signals == []


def test_strategy_service_selects_highest_scoring_signal() -> None:
    low = make_signal(score=60)
    high = make_signal(score=90)
    medium = make_signal(score=75)

    service = StrategyService(
        [
            StaticStrategy(low),
            StaticStrategy(high),
            StaticStrategy(medium),
        ]
    )

    signal = service.select_signal(
        make_market_state()
    )

    assert signal is high


def test_strategy_service_returns_none_when_no_signal_exists() -> None:
    service = StrategyService(
        [
            StaticStrategy(None),
            StaticStrategy(None),
        ]
    )

    signal = service.select_signal(
        make_market_state()
    )

    assert signal is None


def test_strategy_service_works_with_momentum_strategy() -> None:
    service = StrategyService(
        [MomentumStrategy()]
    )

    signal = service.select_signal(
        make_market_state()
    )

    assert signal is not None
    assert signal.symbol == "XAUUSD"


