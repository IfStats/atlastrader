from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.core.enums import (
    OrderSide,
    SignalDirection,
    StrategyType,
    Timeframe,
    TradeEntryType,
)
from packages.core.models import BrokerDeal
from packages.core.trading_journal import (
    TradeDecision,
)
from packages.engine.journal import (
    InMemoryTradeJournal,
)
from packages.engine.trade_reconciliation import (
    TradeOutcomeReconciler,
)

NOW = datetime(
    2026,
    9,
    7,
    16,
    30,
    tzinfo=UTC,
)


def make_decision() -> TradeDecision:
    return TradeDecision(
        id="decision-1",
        symbol="XAUUSD",
        direction=SignalDirection.LONG,
        strategy=StrategyType.MOMENTUM,
        timeframe=Timeframe.M5,
        decision=SignalDirection.LONG,
        status="approved",
        timestamp=NOW,
        signal_score=85.0,
        confidence=0.85,
        entry_price=Decimal("4377.97"),
        stop_loss=Decimal("4372.97"),
        take_profit=Decimal("4387.97"),
        risk_reward_ratio=Decimal(2),
        requested_quantity=Decimal("0.01"),
        order_id="atlas-order-1",
        broker_order_id=None,
        created_at=NOW,
        updated_at=NOW,
    )


def make_deal(
    *,
    deal_id: str,
    order_id: str,
    entry_type: TradeEntryType,
    side: OrderSide,
    quantity: str,
    price: str,
    minute: int,
    profit: str = "0",
) -> BrokerDeal:
    return BrokerDeal(
        broker_deal_id=deal_id,
        broker_order_id=order_id,
        broker_position_id="position-1",
        symbol="XAUUSD",
        side=side,
        entry_type=entry_type,
        quantity=Decimal(quantity),
        price=Decimal(price),
        profit=Decimal(profit),
        timestamp=datetime(
            2026,
            9,
            7,
            16,
            minute,
            tzinfo=UTC,
        ),
    )


def test_journal_can_attach_broker_order_identity() -> None:
    journal = InMemoryTradeJournal()

    decision = make_decision()

    journal.record_decision(
        decision
    )

    updated = decision.model_copy(
        update={
            "broker_order_id": "broker-order-123",
            "updated_at": NOW,
        }
    )

    journal.update_decision(
        updated
    )

    stored = journal.get_decision(
        "decision-1"
    )

    assert stored is not None
    assert (
        stored.broker_order_id
        == "broker-order-123"
    )


def test_broker_order_identity_requires_atlas_order() -> None:
    base = make_decision()

    data = base.model_dump()

    data["order_id"] = None
    data["broker_order_id"] = "broker-1"

    with pytest.raises(
        ValueError,
        match="broker_order_id requires order_id",
    ):
        TradeDecision(
            **data
                
        )


def test_reconciler_preserves_entry_order_lineage() -> None:
    reconciler = TradeOutcomeReconciler()

    deals = [
        make_deal(
            deal_id="entry-1",
            order_id="broker-order-1",
            entry_type=TradeEntryType.IN,
            side=OrderSide.BUY,
            quantity="0.01",
            price="4377.00",
            minute=0,
        ),
        make_deal(
            deal_id="entry-2",
            order_id="broker-order-2",
            entry_type=TradeEntryType.IN,
            side=OrderSide.BUY,
            quantity="0.01",
            price="4379.00",
            minute=1,
        ),
        make_deal(
            deal_id="exit-1",
            order_id="broker-exit-1",
            entry_type=TradeEntryType.OUT,
            side=OrderSide.SELL,
            quantity="0.02",
            price="4385.00",
            minute=5,
            profit="14",
        ),
    ]

    outcomes = reconciler.reconcile(
        deals
    )

    assert len(outcomes) == 1

    assert (
        outcomes[0].entry_broker_order_ids
        == [
            "broker-order-1",
            "broker-order-2",
        ]
    )


def test_reconciler_deduplicates_partial_fill_order_identity() -> None:
    reconciler = TradeOutcomeReconciler()

    deals = [
        make_deal(
            deal_id="entry-1",
            order_id="broker-order-1",
            entry_type=TradeEntryType.IN,
            side=OrderSide.BUY,
            quantity="0.01",
            price="4377.00",
            minute=0,
        ),
        make_deal(
            deal_id="entry-2",
            order_id="broker-order-1",
            entry_type=TradeEntryType.IN,
            side=OrderSide.BUY,
            quantity="0.01",
            price="4378.00",
            minute=1,
        ),
        make_deal(
            deal_id="exit-1",
            order_id="broker-exit-1",
            entry_type=TradeEntryType.OUT,
            side=OrderSide.SELL,
            quantity="0.02",
            price="4385.00",
            minute=5,
            profit="15",
        ),
    ]

    outcome = reconciler.reconcile(
        deals
    )[0]

    assert outcome.entry_broker_order_ids == [
        "broker-order-1"
    ]