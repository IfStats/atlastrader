from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.core.enums import (
    OrderSide,
    SignalDirection,
    StrategyType,
    Timeframe,
)
from packages.learning.models import (
    LearningRecord,
)
from packages.regime.classifier import (
    MarketRegimeClassifier,
)
from packages.regime.models import (
    MomentumRelationship,
    TrendRegime,
    VolatilityRegime,
)

NOW = datetime(
    2026,
    9,
    11,
    12,
    0,
    tzinfo=UTC,
)


def make_record(
    *,
    direction: SignalDirection = (
        SignalDirection.LONG
    ),
    trend_score: float = 0.8,
    momentum_score: float = 0.9,
    volatility_score: float = 0.4,
) -> LearningRecord:
    side = (
        OrderSide.BUY
        if direction
        is SignalDirection.LONG
        else OrderSide.SELL
    )

    return LearningRecord(
        decision_id="decision-1",
        trade_id="trade-1",
        atlas_order_id="atlas-order-1",
        broker_order_id="broker-order-1",
        symbol="XAUUSD",
        strategy=StrategyType.MOMENTUM,
        timeframe=Timeframe.M5,
        direction=direction,
        side=side,
        decision_timestamp=NOW,
        opened_at=NOW,
        closed_at=NOW.replace(
            minute=10
        ),
        signal_score=85.0,
        confidence=0.85,
        requested_quantity=Decimal(
            "0.01"
        ),
        planned_entry_price=Decimal(
            "4377.97"
        ),
        executed_entry_price=Decimal(
            "4378.10"
        ),
        exit_price=Decimal(
            "4388.10"
        ),
        stop_loss=Decimal(
            "4372.97"
        ),
        take_profit=Decimal(
            "4387.97"
        ),
        risk_reward_ratio=Decimal(2),
        planned_risk_amount=Decimal(
            "5.00"
        ),
        planned_risk_percentage=Decimal(
            "0.0027"
        ),
        market_state_price=Decimal(
            "4377.97"
        ),
        trend_score=trend_score,
        momentum_score=momentum_score,
        volatility_score=volatility_score,
        volatility=Decimal(5),
        spread=Decimal(
            "0.20"
        ),
        market_status="open",
        session="london",
        is_tradeable=True,
        gross_pnl=Decimal(10),
        commission=Decimal(0),
        swap=Decimal(0),
        net_pnl=Decimal(10),
        profitable=True,
    )


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (
            0.60,
            TrendRegime.STRONG_UPTREND,
        ),
        (
            0.20,
            TrendRegime.UPTREND,
        ),
        (
            0.00,
            TrendRegime.NEUTRAL,
        ),
        (
            -0.20,
            TrendRegime.DOWNTREND,
        ),
        (
            -0.60,
            TrendRegime.STRONG_DOWNTREND,
        ),
    ],
)
def test_classifies_trend_boundaries(
    score: float,
    expected: TrendRegime,
) -> None:
    classifier = MarketRegimeClassifier()

    assert (
        classifier.classify_trend(score)
        is expected
    )


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (
            0.0,
            VolatilityRegime.LOW,
        ),
        (
            0.329,
            VolatilityRegime.LOW,
        ),
        (
            0.33,
            VolatilityRegime.NORMAL,
        ),
        (
            0.669,
            VolatilityRegime.NORMAL,
        ),
        (
            0.67,
            VolatilityRegime.HIGH,
        ),
        (
            1.0,
            VolatilityRegime.HIGH,
        ),
    ],
)
def test_classifies_volatility_boundaries(
    score: float,
    expected: VolatilityRegime,
) -> None:
    classifier = MarketRegimeClassifier()

    assert (
        classifier.classify_volatility(
            score
        )
        is expected
    )


@pytest.mark.parametrize(
    (
        "direction",
        "score",
        "expected",
    ),
    [
        (
            SignalDirection.LONG,
            0.8,
            MomentumRelationship.ALIGNED,
        ),
        (
            SignalDirection.LONG,
            -0.8,
            MomentumRelationship.CONFLICTING,
        ),
        (
            SignalDirection.LONG,
            0.1,
            MomentumRelationship.WEAK,
        ),
        (
            SignalDirection.SHORT,
            -0.8,
            MomentumRelationship.ALIGNED,
        ),
        (
            SignalDirection.SHORT,
            0.8,
            MomentumRelationship.CONFLICTING,
        ),
        (
            SignalDirection.SHORT,
            -0.1,
            MomentumRelationship.WEAK,
        ),
    ],
)
def test_classifies_momentum_relationship(
    direction: SignalDirection,
    score: float,
    expected: MomentumRelationship,
) -> None:
    classifier = MarketRegimeClassifier()

    assert (
        classifier.classify_momentum(
            direction=direction,
            momentum_score=score,
        )
        is expected
    )


def test_classifies_complete_market_regime() -> None:
    classifier = MarketRegimeClassifier()

    regime = classifier.classify(
        make_record(
            trend_score=0.75,
            momentum_score=0.85,
            volatility_score=0.80,
        )
    )

    assert (
        regime.trend
        is TrendRegime.STRONG_UPTREND
    )

    assert (
        regime.volatility
        is VolatilityRegime.HIGH
    )

    assert (
        regime.momentum
        is MomentumRelationship.ALIGNED
    )

    assert (
        regime.key
        == (
            "strong_uptrend|"
            "high|"
            "aligned"
        )
    )


def test_short_trade_can_be_momentum_aligned() -> None:
    classifier = MarketRegimeClassifier()

    regime = classifier.classify(
        make_record(
            direction=(
                SignalDirection.SHORT
            ),
            trend_score=-0.75,
            momentum_score=-0.85,
            volatility_score=0.50,
        )
    )

    assert (
        regime.trend
        is TrendRegime.STRONG_DOWNTREND
    )

    assert (
        regime.momentum
        is MomentumRelationship.ALIGNED
    )