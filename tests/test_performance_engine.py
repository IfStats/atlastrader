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
from packages.performance.engine import (
    PerformanceEngine,
)

NOW = datetime(
    2026,
    9,
    7,
    12,
    0,
    tzinfo=UTC,
)


def make_record(
    *,
    decision_id: str,
    net_pnl: Decimal,
) -> LearningRecord:
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
        decision_timestamp=NOW,
        opened_at=NOW,
        closed_at=NOW.replace(
            minute=10
        ),
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


def test_empty_dataset_returns_zero_summary() -> None:
    engine = PerformanceEngine()

    summary = engine.summarize(
        []
    )

    assert summary.total_trades == 0
    assert summary.total_net_pnl == Decimal(0)
    assert summary.expectancy == Decimal(0)
    assert summary.profit_factor is None
    assert summary.payoff_ratio is None


def test_calculates_win_loss_and_breakeven_counts() -> None:
    engine = PerformanceEngine()

    summary = engine.summarize(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(10),
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(-5),
            ),
            make_record(
                decision_id="3",
                net_pnl=Decimal(0),
            ),
        ]
    )

    assert summary.total_trades == 3
    assert summary.winning_trades == 1
    assert summary.losing_trades == 1
    assert summary.breakeven_trades == 1

    assert (
        summary.win_rate
        == Decimal(1) / Decimal(3)
    )
    assert (
        summary.loss_rate
        == Decimal(1) / Decimal(3)
    )
    assert (
        summary.breakeven_rate
        == Decimal(1) / Decimal(3)
    )


def test_calculates_net_pnl_and_averages() -> None:
    engine = PerformanceEngine()

    summary = engine.summarize(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(10),
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(20),
            ),
            make_record(
                decision_id="3",
                net_pnl=Decimal(-5),
            ),
            make_record(
                decision_id="4",
                net_pnl=Decimal(-15),
            ),
        ]
    )

    assert (
        summary.total_net_pnl
        == Decimal(10)
    )

    assert (
        summary.total_positive_net_pnl
        == Decimal(30)
    )

    assert (
        summary.total_negative_net_pnl
        == Decimal(-20)
    )

    assert (
        summary.average_net_pnl
        == Decimal("2.5")
    )

    assert (
        summary.average_win
        == Decimal(15)
    )

    assert (
        summary.average_loss
        == Decimal(-10)
    )


def test_calculates_profit_factor_and_payoff_ratio() -> None:
    engine = PerformanceEngine()

    summary = engine.summarize(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(10),
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(20),
            ),
            make_record(
                decision_id="3",
                net_pnl=Decimal(-5),
            ),
            make_record(
                decision_id="4",
                net_pnl=Decimal(-15),
            ),
        ]
    )

    assert (
        summary.profit_factor
        == Decimal("1.5")
    )

    assert (
        summary.payoff_ratio
        == Decimal("1.5")
    )


def test_expectancy_uses_all_trades() -> None:
    engine = PerformanceEngine()

    summary = engine.summarize(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(10),
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(-5),
            ),
            make_record(
                decision_id="3",
                net_pnl=Decimal(0),
            ),
        ]
    )

    expected = (
        Decimal(5)
        / Decimal(3)
    )

    assert (
        summary.expectancy
        == expected
    )

    assert (
        summary.expectancy
        == summary.average_net_pnl
    )


def test_all_winners_have_undefined_loss_ratios() -> None:
    engine = PerformanceEngine()

    summary = engine.summarize(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(10),
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(20),
            ),
        ]
    )

    assert summary.profit_factor is None
    assert summary.payoff_ratio is None
    assert summary.average_loss == Decimal(0)


def test_all_losers_have_zero_profit_factor() -> None:
    engine = PerformanceEngine()

    summary = engine.summarize(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(-5),
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(-15),
            ),
        ]
    )

    assert (
        summary.profit_factor
        == Decimal(0)
    )

    assert (
        summary.average_win
        == Decimal(0)
    )

    assert (
        summary.payoff_ratio
        == Decimal(0)
    )