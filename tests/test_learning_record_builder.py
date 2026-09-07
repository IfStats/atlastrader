from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.core.enums import (
    OrderSide,
    OrderStatus,
    SignalDirection,
    StrategyType,
    Timeframe,
)
from packages.core.trading_journal import (
    TradeDecision,
    TradeOutcome,
)
from packages.learning.builder import (
    LearningRecordBuilder,
)

DECIDED_AT = datetime(
    2026,
    9,
    7,
    10,
    0,
    tzinfo=UTC,
)

OPENED_AT = datetime(
    2026,
    9,
    7,
    10,
    1,
    tzinfo=UTC,
)

CLOSED_AT = datetime(
    2026,
    9,
    7,
    10,
    11,
    tzinfo=UTC,
)


def make_decision(
    *,
    broker_order_id: str | None = "broker-entry-1",
    status: str = "approved",
    symbol: str = "XAUUSD",
) -> TradeDecision:
    return TradeDecision(
        id="decision-1",
        symbol=symbol,
        direction=SignalDirection.LONG,
        strategy=StrategyType.MOMENTUM,
        timeframe=Timeframe.M5,
        decision=SignalDirection.LONG,
        status=status,
        timestamp=DECIDED_AT,
        signal_score=85.0,
        confidence=0.85,
        entry_price=Decimal("4377.97"),
        stop_loss=Decimal("4372.97"),
        take_profit=Decimal("4387.97"),
        risk_reward_ratio=Decimal(2),
        requested_quantity=Decimal("0.01"),
        rationale=[
            "Momentum threshold satisfied",
        ],
        market_state={
            "price": "4377.97",
            "trend_score": 0.8,
            "momentum_score": 0.9,
            "volatility_score": 0.4,
            "volatility": "5",
            "spread": "0.20",
            "market_status": "open",
            "session": "london",
            "is_tradeable": True,
        },
        order_id="atlas-order-1",
        broker_order_id=broker_order_id,
        created_at=DECIDED_AT,
        updated_at=DECIDED_AT,
    )


def make_outcome(
    *,
    entry_broker_order_ids: list[str] | None = None,
    symbol: str = "XAUUSD",
    side: OrderSide = OrderSide.BUY,
    net_pnl: Decimal = Decimal("9.96"),
) -> TradeOutcome:
    return TradeOutcome(
        trade_id="position-1",
        symbol=symbol,
        side=side,
        order_status=OrderStatus.FILLED,
        entry_price=Decimal("4378.10"),
        exit_price=Decimal("4388.10"),
        quantity=Decimal("0.01"),
        gross_pnl=Decimal(10),
        commission=Decimal("-0.04"),
        swap=Decimal(0),
        net_pnl=net_pnl,
        realized=True,
        opened_at=OPENED_AT,
        closed_at=CLOSED_AT,
        exit_reason="take_profit",
        entry_broker_order_ids=(
            entry_broker_order_ids
            if entry_broker_order_ids
            is not None
            else ["broker-entry-1"]
        ),
    )


def test_builds_learning_record_from_exact_lineage() -> None:
    builder = LearningRecordBuilder()

    record = builder.build(
        decision=make_decision(),
        outcome=make_outcome(),
    )

    assert record.decision_id == "decision-1"
    assert record.trade_id == "position-1"

    assert (
        record.atlas_order_id
        == "atlas-order-1"
    )
    assert (
        record.broker_order_id
        == "broker-entry-1"
    )

    assert record.symbol == "XAUUSD"
    assert (
        record.direction
        is SignalDirection.LONG
    )
    assert record.side is OrderSide.BUY

    assert (
        record.planned_entry_price
        == Decimal("4377.97")
    )
    assert (
        record.executed_entry_price
        == Decimal("4378.10")
    )

    assert record.trend_score == 0.8
    assert record.momentum_score == 0.9
    assert (
        record.volatility
        == Decimal(5)
    )
    assert (
        record.spread
        == Decimal("0.20")
    )

    assert (
        record.net_pnl
        == Decimal("9.96")
    )
    assert record.profitable is True


def test_negative_net_pnl_is_labeled_unprofitable() -> None:
    builder = LearningRecordBuilder()

    record = builder.build(
        decision=make_decision(),
        outcome=make_outcome(
            net_pnl=Decimal("-5.04")
        ),
    )

    assert record.profitable is False


def test_rejects_broker_order_identity_mismatch() -> None:
    builder = LearningRecordBuilder()

    with pytest.raises(
        ValueError,
        match=(
            "broker order identities "
            "do not match"
        ),
    ):
        builder.build(
            decision=make_decision(),
            outcome=make_outcome(
                entry_broker_order_ids=[
                    "different-order"
                ]
            ),
        )


def test_rejects_multi_entry_position() -> None:
    builder = LearningRecordBuilder()

    with pytest.raises(
        ValueError,
        match=(
            "exactly one entry broker order"
        ),
    ):
        builder.build(
            decision=make_decision(),
            outcome=make_outcome(
                entry_broker_order_ids=[
                    "broker-entry-1",
                    "broker-entry-2",
                ]
            ),
        )


def test_rejects_unrealized_outcome() -> None:
    builder = LearningRecordBuilder()

    outcome = make_outcome().model_copy(
        update={
            "realized": False,
            "exit_price": None,
            "closed_at": None,
        }
    )

    with pytest.raises(
        ValueError,
        match="realized outcome",
    ):
        builder.build(
            decision=make_decision(),
            outcome=outcome,
        )


def test_rejects_symbol_mismatch() -> None:
    builder = LearningRecordBuilder()

    with pytest.raises(
        ValueError,
        match="symbols do not match",
    ):
        builder.build(
            decision=make_decision(),
            outcome=make_outcome(
                symbol="EURUSD"
            ),
        )


def test_rejects_direction_side_mismatch() -> None:
    builder = LearningRecordBuilder()

    with pytest.raises(
        ValueError,
        match=(
            "direction and outcome side "
            "do not match"
        ),
    ):
        builder.build(
            decision=make_decision(),
            outcome=make_outcome(
                side=OrderSide.SELL
            ),
        )


def test_rejects_missing_required_market_feature() -> None:
    builder = LearningRecordBuilder()

    decision = make_decision()

    market_state = dict(
        decision.market_state
    )
    market_state.pop(
        "trend_score"
    )

    decision = decision.model_copy(
        update={
            "market_state": market_state
        }
    )

    with pytest.raises(
        ValueError,
        match=(
            "Market-state feature missing: "
            "trend_score"
        ),
    ):
        builder.build(
            decision=decision,
            outcome=make_outcome(),
        )