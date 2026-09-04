from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from packages.core.enums import OrderSide, TradeEntryType
from packages.core.models import BrokerDeal
from packages.execution.mock import MockExecutionProvider


def make_deal(
    *,
    deal_id: str,
    symbol: str = "XAUUSD",
    timestamp: datetime,
    entry_type: TradeEntryType = TradeEntryType.IN,
) -> BrokerDeal:
    return BrokerDeal(
        broker_deal_id=deal_id,
        broker_order_id="order-123",
        broker_position_id="position-123",
        symbol=symbol,
        side=OrderSide.BUY,
        entry_type=entry_type,
        quantity=Decimal("0.01"),
        price=Decimal("3300.50"),
        profit=Decimal(0),
        commission=Decimal("-0.02"),
        swap=Decimal(0),
        timestamp=timestamp,
        comment="AtlasTrader",
    )


def test_broker_deal_preserves_broker_identities() -> None:
    timestamp = datetime.now(UTC)

    deal = make_deal(
        deal_id="deal-123",
        timestamp=timestamp,
    )

    assert deal.broker_deal_id == "deal-123"
    assert deal.broker_order_id == "order-123"
    assert deal.broker_position_id == "position-123"


@pytest.mark.asyncio
async def test_mock_execution_returns_trade_history_in_time_range() -> None:
    provider = MockExecutionProvider()

    start = datetime.now(UTC)
    inside = start + timedelta(minutes=5)
    outside = start + timedelta(hours=2)
    end = start + timedelta(minutes=30)

    first = make_deal(
        deal_id="deal-1",
        timestamp=inside,
    )
    second = make_deal(
        deal_id="deal-2",
        timestamp=outside,
    )

    provider.add_trade_deal(first)
    provider.add_trade_deal(second)

    history = await provider.get_trade_history(
        start=start,
        end=end,
    )

    assert history == [first]


@pytest.mark.asyncio
async def test_mock_execution_filters_trade_history_by_symbol() -> None:
    provider = MockExecutionProvider()

    start = datetime.now(UTC)
    end = start + timedelta(minutes=30)

    xau = make_deal(
        deal_id="deal-xau",
        symbol="XAUUSD",
        timestamp=start + timedelta(minutes=5),
    )
    eur = make_deal(
        deal_id="deal-eur",
        symbol="EURUSD",
        timestamp=start + timedelta(minutes=10),
    )

    provider.add_trade_deal(xau)
    provider.add_trade_deal(eur)

    history = await provider.get_trade_history(
        start=start,
        end=end,
        symbol="XAUUSD",
    )

    assert history == [xau]


@pytest.mark.asyncio
async def test_mock_execution_returns_entry_and_exit_deals() -> None:
    provider = MockExecutionProvider()

    timestamp = datetime.now(UTC)

    entry = make_deal(
        deal_id="entry-1",
        timestamp=timestamp,
        entry_type=TradeEntryType.IN,
    )
    exit_deal = make_deal(
        deal_id="exit-1",
        timestamp=timestamp + timedelta(minutes=10),
        entry_type=TradeEntryType.OUT,
    )

    provider.add_trade_deal(entry)
    provider.add_trade_deal(exit_deal)

    history = await provider.get_trade_history(
        start=timestamp - timedelta(minutes=1),
        end=timestamp + timedelta(minutes=20),
    )

    assert history == [entry, exit_deal]
    assert history[0].entry_type is TradeEntryType.IN
    assert history[1].entry_type is TradeEntryType.OUT