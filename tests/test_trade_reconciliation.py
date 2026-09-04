from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.core.enums import OrderSide, TradeEntryType
from packages.core.models import BrokerDeal
from packages.core.trading_journal import TradeOutcome
from packages.engine.trade_reconciliation import TradeOutcomeReconciler


def make_deal(
    *,
    deal_id: str,
    order_id: str,
    position_id: str,
    symbol: str,
    side: OrderSide,
    entry_type: TradeEntryType,
    quantity: str,
    price: str,
    profit: str = "0",
    commission: str = "0",
    swap: str = "0",
    minute: int = 0,
    comment: str | None = None,
) -> BrokerDeal:
    return BrokerDeal(
        broker_deal_id=deal_id,
        broker_order_id=order_id,
        broker_position_id=position_id,
        symbol=symbol,
        side=side,
        entry_type=entry_type,
        quantity=Decimal(quantity),
        price=Decimal(price),
        profit=Decimal(profit),
        commission=Decimal(commission),
        swap=Decimal(swap),
        timestamp=datetime(
            2026,
            9,
            4,
            10,
            minute,
            tzinfo=UTC,
        ),
        comment=comment,
    )


def test_reconciles_buy_position_into_realized_outcome() -> None:
    reconciler = TradeOutcomeReconciler()

    deals = [
        make_deal(
            deal_id="entry-1",
            order_id="order-entry",
            position_id="position-1",
            symbol="XAUUSD",
            side=OrderSide.BUY,
            entry_type=TradeEntryType.IN,
            quantity="0.01",
            price="4377.97",
            commission="-0.02",
        ),
        make_deal(
            deal_id="exit-1",
            order_id="order-exit",
            position_id="position-1",
            symbol="XAUUSD",
            side=OrderSide.SELL,
            entry_type=TradeEntryType.OUT,
            quantity="0.01",
            price="4387.97",
            profit="10",
            commission="-0.02",
            minute=5,
            comment="[tp 4387.97]",
        ),
    ]

    outcomes = reconciler.reconcile(deals)

    assert len(outcomes) == 1

    outcome = outcomes[0]

    assert isinstance(outcome, TradeOutcome)
    assert outcome.trade_id == "position-1"
    assert outcome.symbol == "XAUUSD"
    assert outcome.side is OrderSide.BUY
    assert outcome.quantity == Decimal("0.01")
    assert outcome.entry_price == Decimal("4377.97")
    assert outcome.exit_price == Decimal("4387.97")
    assert outcome.gross_pnl == Decimal(10)
    assert outcome.commission == Decimal("-0.04")
    assert outcome.swap == Decimal(0)
    assert outcome.net_pnl == Decimal("9.96")
    assert outcome.realized is True
    assert outcome.exit_reason == "take_profit"


def test_reconciles_sell_position_into_realized_outcome() -> None:
    reconciler = TradeOutcomeReconciler()

    deals = [
        make_deal(
            deal_id="entry-1",
            order_id="order-entry",
            position_id="position-2",
            symbol="EURUSD",
            side=OrderSide.SELL,
            entry_type=TradeEntryType.IN,
            quantity="0.10",
            price="1.1700",
            commission="-0.01",
        ),
        make_deal(
            deal_id="exit-1",
            order_id="order-exit",
            position_id="position-2",
            symbol="EURUSD",
            side=OrderSide.BUY,
            entry_type=TradeEntryType.OUT,
            quantity="0.10",
            price="1.1650",
            profit="50",
            commission="-0.01",
            minute=5,
        ),
    ]

    outcomes = reconciler.reconcile(deals)

    assert len(outcomes) == 1

    outcome = outcomes[0]

    assert outcome.side is OrderSide.SELL
    assert outcome.entry_price == Decimal("1.1700")
    assert outcome.exit_price == Decimal("1.1650")
    assert outcome.gross_pnl == Decimal(50)
    assert outcome.net_pnl == Decimal("49.98")


def test_reconciles_actual_xauusd_stop_loss_trade() -> None:
    reconciler = TradeOutcomeReconciler()

    deals = [
        make_deal(
            deal_id="369296004",
            order_id="528120643",
            position_id="528120643",
            symbol="XAUUSD",
            side=OrderSide.BUY,
            entry_type=TradeEntryType.IN,
            quantity="0.01",
            price="4377.97",
            commission="-0.02",
            minute=0,
            comment="AtlasTrader",
        ),
        make_deal(
            deal_id="369299381",
            order_id="528125150",
            position_id="528120643",
            symbol="XAUUSD",
            side=OrderSide.SELL,
            entry_type=TradeEntryType.OUT,
            quantity="0.01",
            price="4372.97",
            profit="-5.0",
            commission="-0.02",
            minute=10,
            comment="[sl 4372.97]",
        ),
    ]

    outcomes = reconciler.reconcile(deals)

    assert len(outcomes) == 1

    outcome = outcomes[0]

    assert outcome.trade_id == "528120643"
    assert outcome.entry_price == Decimal("4377.97")
    assert outcome.exit_price == Decimal("4372.97")
    assert outcome.quantity == Decimal("0.01")
    assert outcome.gross_pnl == Decimal("-5.0")
    assert outcome.commission == Decimal("-0.04")
    assert outcome.swap == Decimal(0)
    assert outcome.net_pnl == Decimal("-5.04")
    assert outcome.realized is True
    assert outcome.exit_reason == "stop_loss"


def test_returns_no_outcome_for_open_position() -> None:
    reconciler = TradeOutcomeReconciler()

    deals = [
        make_deal(
            deal_id="entry-1",
            order_id="order-entry",
            position_id="position-open",
            symbol="XAUUSD",
            side=OrderSide.BUY,
            entry_type=TradeEntryType.IN,
            quantity="0.01",
            price="4377.97",
        ),
    ]

    outcomes = reconciler.reconcile(deals)

    assert outcomes == []


def test_returns_no_outcome_for_partial_exit() -> None:
    reconciler = TradeOutcomeReconciler()

    deals = [
        make_deal(
            deal_id="entry-1",
            order_id="order-entry",
            position_id="position-partial",
            symbol="XAUUSD",
            side=OrderSide.BUY,
            entry_type=TradeEntryType.IN,
            quantity="0.02",
            price="4377.97",
        ),
        make_deal(
            deal_id="exit-1",
            order_id="order-exit",
            position_id="position-partial",
            symbol="XAUUSD",
            side=OrderSide.SELL,
            entry_type=TradeEntryType.OUT,
            quantity="0.01",
            price="4372.97",
            profit="-5",
            minute=5,
        ),
    ]

    outcomes = reconciler.reconcile(deals)

    assert outcomes == []


def test_rejects_deal_without_position_identity() -> None:
    reconciler = TradeOutcomeReconciler()

    deal = BrokerDeal(
        broker_deal_id="deal-1",
        broker_order_id="order-1",
        broker_position_id=None,
        symbol="XAUUSD",
        side=OrderSide.BUY,
        entry_type=TradeEntryType.IN,
        quantity=Decimal("0.01"),
        price=Decimal("4377.97"),
        timestamp=datetime(2026, 9, 4, 10, 0, tzinfo=UTC),
    )

    with pytest.raises(
        ValueError,
        match="no position ID",
    ):
        reconciler.reconcile([deal])


def test_rejects_inconsistent_entry_sides() -> None:
    reconciler = TradeOutcomeReconciler()

    deals = [
        make_deal(
            deal_id="entry-1",
            order_id="order-1",
            position_id="position-3",
            symbol="XAUUSD",
            side=OrderSide.BUY,
            entry_type=TradeEntryType.IN,
            quantity="0.01",
            price="4377.97",
        ),
        make_deal(
            deal_id="entry-2",
            order_id="order-2",
            position_id="position-3",
            symbol="XAUUSD",
            side=OrderSide.SELL,
            entry_type=TradeEntryType.IN,
            quantity="0.01",
            price="4378.00",
        ),
        make_deal(
            deal_id="exit-1",
            order_id="order-3",
            position_id="position-3",
            symbol="XAUUSD",
            side=OrderSide.SELL,
            entry_type=TradeEntryType.OUT,
            quantity="0.02",
            price="4370.00",
            profit="-10",
            minute=5,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="inconsistent sides",
    ):
        reconciler.reconcile(deals)


def test_aggregates_multiple_entry_and_exit_deals() -> None:
    reconciler = TradeOutcomeReconciler()

    deals = [
        make_deal(
            deal_id="entry-1",
            order_id="order-1",
            position_id="position-4",
            symbol="XAUUSD",
            side=OrderSide.BUY,
            entry_type=TradeEntryType.IN,
            quantity="0.01",
            price="4370.00",
            commission="-0.01",
        ),
        make_deal(
            deal_id="entry-2",
            order_id="order-2",
            position_id="position-4",
            symbol="XAUUSD",
            side=OrderSide.BUY,
            entry_type=TradeEntryType.IN,
            quantity="0.01",
            price="4380.00",
            commission="-0.01",
            minute=1,
        ),
        make_deal(
            deal_id="exit-1",
            order_id="order-3",
            position_id="position-4",
            symbol="XAUUSD",
            side=OrderSide.SELL,
            entry_type=TradeEntryType.OUT,
            quantity="0.01",
            price="4385.00",
            profit="15",
            commission="-0.01",
            minute=5,
        ),
        make_deal(
            deal_id="exit-2",
            order_id="order-4",
            position_id="position-4",
            symbol="XAUUSD",
            side=OrderSide.SELL,
            entry_type=TradeEntryType.OUT,
            quantity="0.01",
            price="4390.00",
            profit="10",
            commission="-0.01",
            minute=6,
        ),
    ]

    outcomes = reconciler.reconcile(deals)

    assert len(outcomes) == 1

    outcome = outcomes[0]

    assert outcome.quantity == Decimal("0.02")
    assert outcome.entry_price == Decimal(4375)
    assert outcome.exit_price == Decimal("4387.5")
    assert outcome.gross_pnl == Decimal(25)
    assert outcome.commission == Decimal("-0.04")
    assert outcome.net_pnl == Decimal("24.96")