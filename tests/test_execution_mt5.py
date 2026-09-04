from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import MetaTrader5 as mt5  # type: ignore[import-untyped]

from packages.core.enums import (
    AssetClass,
    OrderSide,
    OrderStatus,
    OrderType,
    TradeEntryType,
)
from packages.core.models import Instrument, Order
from packages.execution.mt5 import MT5ExecutionProvider


def make_order() -> Order:
    now = datetime.now(UTC)

    return Order(
        id="atlas-order-1",
        symbol="XAUUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        status=OrderStatus.PENDING,
        quantity=Decimal("0.01"),
        stop_loss=Decimal(3295),
        take_profit=Decimal(3310),
        created_at=now,
        updated_at=now,
    )


def make_instrument() -> Instrument:
    now = datetime.now(UTC)

    return Instrument(
        symbol="XAUUSD",
        name="XAUUSD",
        asset_class=AssetClass.METAL,
        quote_currency="USD",
        broker_symbol="XAUUSD",
        tick_size=Decimal("0.01"),
        contract_size=Decimal(100),
        min_volume=Decimal("0.01"),
        max_volume=Decimal(100),
        volume_step=Decimal("0.01"),
        price_precision=2,
        volume_precision=2,
        enabled=True,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_submit_order_preserves_broker_order_id() -> None:
    provider = MT5ExecutionProvider()

    result = SimpleNamespace(
        retcode=10009,
        price=3300.50,
        order=123456789,
        deal=987654321,
        comment="Request executed",
    )

    tick = SimpleNamespace(
        ask=3300.50,
        bid=3300.45,
    )

    with (
        patch(
            "packages.execution.mt5.mt5.terminal_info",
             return_value=SimpleNamespace(),
        ),
        patch(
            "packages.execution.mt5.mt5.symbol_info",
            return_value=SimpleNamespace(
                name="XAUUSD",
                visible=True,
                trade_tick_size=0.01,
                trade_contract_size=100.0,
                volume_min=0.01,
                volume_max=100.0,
                volume_step=0.01,
                digits=2,
                currency_profit="USD",
                filling_mode=0,
                path="Forex\\Metals",
            ),
        ),
        patch(
            "packages.execution.mt5.mt5.symbol_info_tick",
            return_value=tick,
        ),
        patch(
            "packages.execution.mt5.mt5.order_send",
            return_value=result,
        ),
    ):
        provider._connected = True

        filled_order = await provider.submit_order(make_order())

    assert filled_order.status is OrderStatus.FILLED
    assert filled_order.price == Decimal("3300.5")
    assert filled_order.broker_order_id == "123456789"


@pytest.mark.asyncio
async def test_submit_order_does_not_use_deal_as_broker_order_id() -> None:
    provider = MT5ExecutionProvider()

    result = SimpleNamespace(
        retcode=10009,
        price=3300.50,
        order=123456789,
        deal=987654321,
        comment="Request executed",
    )

    tick = SimpleNamespace(
        ask=3300.50,
        bid=3300.45,
    )

    with (
        patch(
            "packages.execution.mt5.mt5.terminal_info",
             return_value=SimpleNamespace(),
        ),
        patch(
            "packages.execution.mt5.mt5.symbol_info",
            return_value=SimpleNamespace(
                name="XAUUSD",
                visible=True,
                trade_tick_size=0.01,
                trade_contract_size=100.0,
                volume_min=0.01,
                volume_max=100.0,
                volume_step=0.01,
                digits=2,
                currency_profit="USD",
                filling_mode=0,
                path="Forex\\Metals",
            ),
        ),
        patch(
            "packages.execution.mt5.mt5.symbol_info_tick",
            return_value=tick,
        ),
        patch(
            "packages.execution.mt5.mt5.order_send",
            return_value=result,
        ),
    ):
        provider._connected = True

        filled_order = await provider.submit_order(make_order())

    assert filled_order.broker_order_id != str(result.deal)
    assert filled_order.broker_order_id == str(result.order)

@pytest.mark.asyncio
async def test_get_trade_history_maps_mt5_entry_and_exit_deals() -> None:
    provider = MT5ExecutionProvider()

    start = datetime(2026, 9, 4, 10, 0, tzinfo=UTC)
    end = datetime(2026, 9, 4, 11, 0, tzinfo=UTC)

    entry_time = int(start.timestamp())
    exit_time = int((start + timedelta(minutes=10)).timestamp())

    deals = [
        SimpleNamespace(
            ticket=369296004,
            order=528120643,
            position_id=528120643,
            symbol="XAUUSD",
            type=mt5.DEAL_TYPE_BUY,
            entry=mt5.DEAL_ENTRY_IN,
            volume=0.01,
            price=4377.97,
            profit=0.0,
            commission=-0.02,
            swap=0.0,
            time=entry_time,
            comment="AtlasTrader",
        ),
        SimpleNamespace(
            ticket=369299381,
            order=528125150,
            position_id=528120643,
            symbol="XAUUSD",
            type=mt5.DEAL_TYPE_SELL,
            entry=mt5.DEAL_ENTRY_OUT,
            volume=0.01,
            price=4372.97,
            profit=-5.0,
            commission=-0.02,
            swap=0.0,
            time=exit_time,
            comment="[sl 4372.97]",
        ),
    ]

    with (
        patch(
            "packages.execution.mt5.mt5.terminal_info",
            return_value=SimpleNamespace(),
        ),
        patch(
            "packages.execution.mt5.mt5.history_deals_get",
            return_value=deals,
        ),
    ):
        provider._connected = True

        history = await provider.get_trade_history(
            start=start,
            end=end,
            symbol="XAUUSD",
        )

    assert len(history) == 2

    entry = history[0]
    assert entry.broker_deal_id == "369296004"
    assert entry.broker_order_id == "528120643"
    assert entry.broker_position_id == "528120643"
    assert entry.side is OrderSide.BUY
    assert entry.entry_type is TradeEntryType.IN
    assert entry.quantity == Decimal("0.01")
    assert entry.price == Decimal("4377.97")
    assert entry.commission == Decimal("-0.02")

    exit_deal = history[1]
    assert exit_deal.broker_deal_id == "369299381"
    assert exit_deal.broker_order_id == "528125150"
    assert exit_deal.broker_position_id == "528120643"
    assert exit_deal.side is OrderSide.SELL
    assert exit_deal.entry_type is TradeEntryType.OUT
    assert exit_deal.profit == Decimal("-5.0")
    assert exit_deal.commission == Decimal("-0.02")
    assert exit_deal.comment == "[sl 4372.97]"


@pytest.mark.asyncio
async def test_get_trade_history_filters_symbol() -> None:
    provider = MT5ExecutionProvider()

    start = datetime(2026, 9, 4, 10, 0, tzinfo=UTC)
    end = datetime(2026, 9, 4, 11, 0, tzinfo=UTC)

    deal = SimpleNamespace(
        ticket=1001,
        order=2001,
        position_id=3001,
        symbol="EURUSD",
        type=mt5.DEAL_TYPE_BUY,
        entry=mt5.DEAL_ENTRY_IN,
        volume=0.10,
        price=1.1700,
        profit=0.0,
        commission=0.0,
        swap=0.0,
        time=int(start.timestamp()),
        comment="test",
    )

    with (
        patch(
            "packages.execution.mt5.mt5.terminal_info",
            return_value=SimpleNamespace(),
        ),
        patch(
            "packages.execution.mt5.mt5.history_deals_get",
            return_value=[deal],
        ),
    ):
        provider._connected = True

        history = await provider.get_trade_history(
            start=start,
            end=end,
            symbol="XAUUSD",
        )

    assert history == []


@pytest.mark.asyncio
async def test_get_trade_history_raises_when_mt5_history_fails() -> None:
    provider = MT5ExecutionProvider()

    start = datetime(2026, 9, 4, 10, 0, tzinfo=UTC)
    end = datetime(2026, 9, 4, 11, 0, tzinfo=UTC)

    with (
        patch(
            "packages.execution.mt5.mt5.terminal_info",
            return_value=SimpleNamespace(),
        ),
        patch(
            "packages.execution.mt5.mt5.history_deals_get",
            return_value=None,
        ),
        patch(
            "packages.execution.mt5.mt5.last_error",
            return_value=(-1, "History unavailable"),
        ),
    ):
        provider._connected = True

        with pytest.raises(
            RuntimeError,
            match="Unable to retrieve MT5 trade history",
        ):
            await provider.get_trade_history(
                start=start,
                end=end,
            )