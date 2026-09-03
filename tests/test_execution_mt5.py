from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from packages.core.enums import AssetClass, OrderSide, OrderStatus, OrderType
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