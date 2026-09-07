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
from packages.performance.segmentation import (
    UNSPECIFIED_SESSION,
    SegmentedPerformanceEngine,
)

NOW = datetime(
    2026,
    9,
    7,
    13,
    0,
    tzinfo=UTC,
)


def make_record(
    *,
    decision_id: str,
    net_pnl: Decimal,
    strategy: StrategyType = (
        StrategyType.MOMENTUM
    ),
    symbol: str = "XAUUSD",
    timeframe: Timeframe = Timeframe.M5,
    session: str | None = "london",
) -> LearningRecord:
    return LearningRecord(
        decision_id=decision_id,
        trade_id=f"trade-{decision_id}",
        atlas_order_id=(
            f"atlas-{decision_id}"
        ),
        broker_order_id=(
            f"broker-{decision_id}"
        ),
        symbol=symbol,
        strategy=strategy,
        timeframe=timeframe,
        direction=SignalDirection.LONG,
        side=OrderSide.BUY,
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
        market_state_price=Decimal(
            "4377.97"
        ),
        trend_score=0.8,
        momentum_score=0.9,
        volatility_score=0.4,
        volatility=Decimal(5),
        spread=Decimal(
            "0.20"
        ),
        market_status="open",
        session=session,
        is_tradeable=True,
        gross_pnl=net_pnl,
        commission=Decimal(0),
        swap=Decimal(0),
        net_pnl=net_pnl,
        profitable=(
            net_pnl > Decimal(0)
        ),
    )


def test_segmented_summary_preserves_overall() -> None:
    engine = SegmentedPerformanceEngine()

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


def test_segments_by_strategy() -> None:
    engine = SegmentedPerformanceEngine()

    result = engine.summarize(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(10),
                strategy=(
                    StrategyType.MOMENTUM
                ),
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(-5),
                strategy=(
                    StrategyType.MEAN_REVERSION
                ),
            ),
        ]
    )

    assert (
        result
        .by_strategy["momentum"]
        .total_net_pnl
        == Decimal(10)
    )

    assert (
        result
        .by_strategy["mean_reversion"]
        .total_net_pnl
        == Decimal(-5)
    )


def test_segments_by_symbol() -> None:
    engine = SegmentedPerformanceEngine()

    result = engine.summarize(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(10),
                symbol="XAUUSD",
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(-4),
                symbol="EURUSD",
            ),
        ]
    )

    assert (
        result
        .by_symbol["XAUUSD"]
        .expectancy
        == Decimal(10)
    )

    assert (
        result
        .by_symbol["EURUSD"]
        .expectancy
        == Decimal(-4)
    )


def test_segments_by_timeframe() -> None:
    engine = SegmentedPerformanceEngine()

    result = engine.summarize(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(10),
                timeframe=Timeframe.M5,
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(-5),
                timeframe=Timeframe.M15,
            ),
        ]
    )

    assert (
        result
        .by_timeframe["5m"]
        .total_trades
        == 1
    )

    assert (
        result
        .by_timeframe["15m"]
        .total_trades
        == 1
    )


def test_segments_by_session() -> None:
    engine = SegmentedPerformanceEngine()

    result = engine.summarize(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(10),
                session="London",
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(-5),
                session="NEW YORK",
            ),
        ]
    )

    assert (
        result
        .by_session["london"]
        .total_net_pnl
        == Decimal(10)
    )

    assert (
        result
        .by_session["new york"]
        .total_net_pnl
        == Decimal(-5)
    )


def test_unspecified_session_is_preserved() -> None:
    engine = SegmentedPerformanceEngine()

    result = engine.summarize(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(10),
                session=None,
            )
        ]
    )

    assert (
        result
        .by_session[
            UNSPECIFIED_SESSION
        ]
        .total_trades
        == 1
    )


def test_each_dimension_partitions_all_records() -> None:
    engine = SegmentedPerformanceEngine()

    result = engine.summarize(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(10),
                strategy=(
                    StrategyType.MOMENTUM
                ),
                symbol="XAUUSD",
                timeframe=Timeframe.M5,
                session="london",
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(-5),
                strategy=(
                    StrategyType.MEAN_REVERSION
                ),
                symbol="EURUSD",
                timeframe=Timeframe.M15,
                session=None,
            ),
        ]
    )

    assert sum(
        summary.total_trades
        for summary
        in result.by_strategy.values()
    ) == 2

    assert sum(
        summary.total_trades
        for summary
        in result.by_symbol.values()
    ) == 2

    assert sum(
        summary.total_trades
        for summary
        in result.by_timeframe.values()
    ) == 2

    assert sum(
        summary.total_trades
        for summary
        in result.by_session.values()
    ) == 2


def test_empty_dataset_returns_empty_segments() -> None:
    engine = SegmentedPerformanceEngine()

    result = engine.summarize(
        []
    )

    assert result.overall.total_trades == 0

    assert result.by_strategy == {}
    assert result.by_symbol == {}
    assert result.by_timeframe == {}
    assert result.by_session == {}