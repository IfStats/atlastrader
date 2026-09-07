from datetime import UTC, datetime, timedelta
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
from packages.performance.path import (
    PathPerformanceEngine,
)

BASE_TIME = datetime(
    2026,
    9,
    7,
    10,
    0,
    tzinfo=UTC,
)


def make_record(
    *,
    decision_id: str,
    net_pnl: Decimal,
    close_offset: int,
) -> LearningRecord:
    opened_at = (
        BASE_TIME
        + timedelta(
            minutes=close_offset - 1
        )
    )

    closed_at = (
        BASE_TIME
        + timedelta(
            minutes=close_offset
        )
    )

    return LearningRecord(
        decision_id=decision_id,
        trade_id=f"trade-{decision_id}",
        atlas_order_id=f"atlas-{decision_id}",
        broker_order_id=f"broker-{decision_id}",
        symbol="XAUUSD",
        strategy=StrategyType.MOMENTUM,
        timeframe=Timeframe.M5,
        direction=SignalDirection.LONG,
        side=OrderSide.BUY,
        decision_timestamp=opened_at,
        opened_at=opened_at,
        closed_at=closed_at,
        signal_score=85.0,
        confidence=0.85,
        requested_quantity=Decimal("0.01"),
        planned_entry_price=Decimal("4377.97"),
        executed_entry_price=Decimal("4378.10"),
        exit_price=Decimal("4388.10"),
        stop_loss=Decimal("4372.97"),
        take_profit=Decimal("4387.97"),
        risk_reward_ratio=Decimal(2),
        market_state_price=Decimal("4377.97"),
        trend_score=0.8,
        momentum_score=0.9,
        volatility_score=0.4,
        volatility=Decimal(5),
        spread=Decimal("0.20"),
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


def test_empty_dataset_returns_zero_path_statistics() -> None:
    engine = PathPerformanceEngine()

    summary = engine.summarize(
        []
    )

    assert summary.total_trades == 0
    assert (
        summary.ending_cumulative_pnl
        == Decimal(0)
    )
    assert (
        summary.max_drawdown
        == Decimal(0)
    )
    assert summary.max_consecutive_wins == 0
    assert summary.max_consecutive_losses == 0


def test_calculates_absolute_closed_trade_drawdown() -> None:
    engine = PathPerformanceEngine()

    summary = engine.summarize(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(10),
                close_offset=1,
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(-4),
                close_offset=2,
            ),
            make_record(
                decision_id="3",
                net_pnl=Decimal(-8),
                close_offset=3,
            ),
            make_record(
                decision_id="4",
                net_pnl=Decimal(5),
                close_offset=4,
            ),
            make_record(
                decision_id="5",
                net_pnl=Decimal(-2),
                close_offset=5,
            ),
        ]
    )

    assert (
        summary.ending_cumulative_pnl
        == Decimal(1)
    )

    assert (
        summary.peak_cumulative_pnl
        == Decimal(10)
    )

    assert (
        summary.minimum_cumulative_pnl
        == Decimal(-2)
    )

    assert (
        summary.max_drawdown
        == Decimal(12)
    )

    assert (
        summary.max_drawdown_peak_pnl
        == Decimal(10)
    )

    assert (
        summary.max_drawdown_trough_pnl
        == Decimal(-2)
    )


def test_first_loss_draws_down_from_zero_baseline() -> None:
    engine = PathPerformanceEngine()

    summary = engine.summarize(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(-5),
                close_offset=1,
            )
        ]
    )

    assert (
        summary.max_drawdown
        == Decimal(5)
    )

    assert (
        summary.max_drawdown_peak_pnl
        == Decimal(0)
    )

    assert (
        summary.max_drawdown_trough_pnl
        == Decimal(-5)
    )


def test_all_winners_have_zero_drawdown() -> None:
    engine = PathPerformanceEngine()

    summary = engine.summarize(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(5),
                close_offset=1,
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(10),
                close_offset=2,
            ),
        ]
    )

    assert (
        summary.max_drawdown
        == Decimal(0)
    )

    assert (
        summary.peak_cumulative_pnl
        == Decimal(15)
    )


def test_calculates_win_loss_and_breakeven_streaks() -> None:
    engine = PathPerformanceEngine()

    records = [
        make_record(
            decision_id="1",
            net_pnl=Decimal(10),
            close_offset=1,
        ),
        make_record(
            decision_id="2",
            net_pnl=Decimal(5),
            close_offset=2,
        ),
        make_record(
            decision_id="3",
            net_pnl=Decimal(-1),
            close_offset=3,
        ),
        make_record(
            decision_id="4",
            net_pnl=Decimal(-2),
            close_offset=4,
        ),
        make_record(
            decision_id="5",
            net_pnl=Decimal(-3),
            close_offset=5,
        ),
        make_record(
            decision_id="6",
            net_pnl=Decimal(0),
            close_offset=6,
        ),
        make_record(
            decision_id="7",
            net_pnl=Decimal(0),
            close_offset=7,
        ),
        make_record(
            decision_id="8",
            net_pnl=Decimal(4),
            close_offset=8,
        ),
    ]

    summary = engine.summarize(
        records
    )

    assert (
        summary.max_consecutive_wins
        == 2
    )

    assert (
        summary.max_consecutive_losses
        == 3
    )

    assert (
        summary.max_consecutive_breakevens
        == 2
    )

    assert (
        summary.ending_win_streak
        == 1
    )

    assert (
        summary.ending_loss_streak
        == 0
    )

    assert (
        summary.ending_breakeven_streak
        == 0
    )


def test_records_are_processed_by_close_time() -> None:
    engine = PathPerformanceEngine()

    summary = engine.summarize(
        [
            make_record(
                decision_id="3",
                net_pnl=Decimal(5),
                close_offset=3,
            ),
            make_record(
                decision_id="1",
                net_pnl=Decimal(10),
                close_offset=1,
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(-15),
                close_offset=2,
            ),
        ]
    )

    assert (
        summary.max_drawdown
        == Decimal(15)
    )

    assert (
        summary.ending_cumulative_pnl
        == Decimal(0)
    )