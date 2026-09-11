from datetime import UTC, datetime
from decimal import Decimal

from packages.core.enums import (
    OrderSide,
    SignalDirection,
    StrategyType,
    Timeframe,
)
from packages.learning.models import (
    LearningRecord,
)
from packages.regime.performance import (
    RegimePerformanceEngine,
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
    decision_id: str,
    net_pnl: Decimal,
    direction: SignalDirection = (
        SignalDirection.LONG
    ),
    trend_score: float = 0.8,
    momentum_score: float = 0.8,
    volatility_score: float = 0.5,
) -> LearningRecord:
    side = (
        OrderSide.BUY
        if direction
        is SignalDirection.LONG
        else OrderSide.SELL
    )

    return LearningRecord(
        decision_id=decision_id,
        trade_id=f"trade-{decision_id}",
        atlas_order_id=(
            f"atlas-{decision_id}"
        ),
        broker_order_id=(
            f"broker-{decision_id}"
        ),
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
        gross_pnl=net_pnl,
        commission=Decimal(0),
        swap=Decimal(0),
        net_pnl=net_pnl,
        profitable=(
            net_pnl > Decimal(0)
        ),
    )


def test_regime_summary_preserves_overall() -> None:
    engine = RegimePerformanceEngine()

    result = engine.summarize(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(10),
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(-5),
            ),
        ]
    )

    assert (
        result.overall.total_trades
        == 2
    )

    assert (
        result.overall.total_net_pnl
        == Decimal(5)
    )


def test_groups_identical_regimes() -> None:
    engine = RegimePerformanceEngine()

    result = engine.summarize(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(10),
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(-4),
            ),
        ]
    )

    key = (
        "strong_uptrend|"
        "normal|"
        "aligned"
    )

    assert (
        result
        .by_regime[key]
        .total_trades
        == 2
    )

    assert (
        result
        .by_regime[key]
        .total_net_pnl
        == Decimal(6)
    )


def test_separates_distinct_regimes() -> None:
    engine = RegimePerformanceEngine()

    result = engine.summarize(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(12),
                trend_score=0.8,
                momentum_score=0.8,
                volatility_score=0.8,
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(-5),
                trend_score=0.0,
                momentum_score=0.0,
                volatility_score=0.1,
            ),
        ]
    )

    assert (
        len(result.by_regime)
        == 2
    )

    assert (
        result.by_regime[
            "strong_uptrend|high|aligned"
        ].expectancy
        == Decimal(12)
    )

    assert (
        result.by_regime[
            "neutral|low|weak"
        ].expectancy
        == Decimal(-5)
    )


def test_short_aligned_regime_is_grouped() -> None:
    engine = RegimePerformanceEngine()

    result = engine.summarize(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(8),
                direction=SignalDirection.SHORT,
                trend_score=-0.8,
                momentum_score=-0.8,
                volatility_score=0.5,
            )
        ]
    )

    key = (
        "strong_downtrend|"
        "normal|"
        "aligned"
    )

    assert (
        result
        .by_regime[key]
        .total_trades
        == 1
    )


def test_regime_partitions_cover_all_records() -> None:
    engine = RegimePerformanceEngine()

    result = engine.summarize(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(10),
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(-5),
                trend_score=0.0,
                momentum_score=-0.8,
                volatility_score=0.8,
            ),
            make_record(
                decision_id="3",
                net_pnl=Decimal(3),
                direction=SignalDirection.SHORT,
                trend_score=-0.8,
                momentum_score=-0.8,
                volatility_score=0.2,
            ),
        ]
    )

    segmented_total = sum(
        summary.total_trades
        for summary
        in result.by_regime.values()
    )

    assert (
        segmented_total
        == result.overall.total_trades
    )


def test_empty_dataset_returns_no_regimes() -> None:
    engine = RegimePerformanceEngine()

    result = engine.summarize([])

    assert (
        result.overall.total_trades
        == 0
    )

    assert result.by_regime == {}