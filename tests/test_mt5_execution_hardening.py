from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from packages.core.enums import OrderSide, OrderStatus, OrderType
from packages.core.models import Order
from packages.execution.mt5 import MT5ExecutionProvider


def make_provider() -> MT5ExecutionProvider:
    return MT5ExecutionProvider(
        login=123456,
        password="test-password",
        server="Test-Server",
    )


def make_order(
    *,
    side: OrderSide = OrderSide.BUY,
    quantity: Decimal = Decimal("0.01"),
) -> Order:
    return Order(
        id="test-order",
        symbol="XAUUSD",
        side=side,
        order_type=OrderType.MARKET,
        status=OrderStatus.PENDING,
        quantity=quantity,
        stop_loss=Decimal(3345),
        take_profit=Decimal(3360),
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )


def make_instrument_info() -> MagicMock:
    info = MagicMock()
    info.name = "XAUUSD"
    info.path = "Forex\\Metals"
    info.trade_tick_size = 0.01
    info.trade_contract_size = 100.0
    info.volume_min = 0.01
    info.volume_max = 100.0
    info.volume_step = 0.01
    info.digits = 2
    info.visible = True
    info.trade_mode = 0
    info.currency_base = "XAU"
    info.currency_profit = "USD"
    info.exchange = None
    return info


@pytest.mark.asyncio
async def test_connect_is_idempotent() -> None:
    provider = make_provider()

    with patch(
        "packages.execution.mt5.mt5.initialize",
        return_value=True,
    ) as initialize:
        await provider.connect()
        await provider.connect()

    initialize.assert_called_once()


@pytest.mark.asyncio
async def test_disconnect_is_idempotent() -> None:
    provider = make_provider()

    with patch(
        "packages.execution.mt5.mt5.shutdown",
    ) as shutdown:
        await provider.disconnect()
        await provider.disconnect()

    shutdown.assert_not_called()
    assert await provider.is_connected() is False


@pytest.mark.asyncio
async def test_submit_buy_order_uses_ask_price() -> None:
    provider = make_provider()
    order = make_order(side=OrderSide.BUY)

    info = make_instrument_info()

    tick = MagicMock()
    tick.ask = 3350.25
    tick.bid = 3350.05

    result = MagicMock()
    result.retcode = 10009
    result.price = 3350.25

    with (
        patch(
            "packages.execution.mt5.mt5.terminal_info",
            return_value=MagicMock(),
        ),
        patch(
            "packages.execution.mt5.mt5.symbol_info",
            return_value=info,
        ),
        patch(
            "packages.execution.mt5.mt5.symbol_info_tick",
            return_value=tick,
        ),
        patch(
            "packages.execution.mt5.mt5.order_send",
            return_value=result,
        ) as order_send,
    ):
        provider._connected = True

        submitted = await provider.submit_order(order)

    request = order_send.call_args.args[0]

    assert request["price"] == 3350.25
    assert submitted.status is OrderStatus.FILLED
    assert submitted.price == Decimal("3350.25")


@pytest.mark.asyncio
async def test_submit_sell_order_uses_bid_price() -> None:
    provider = make_provider()
    order = make_order(side=OrderSide.SELL)

    info = make_instrument_info()

    tick = MagicMock()
    tick.ask = 3350.25
    tick.bid = 3350.05

    result = MagicMock()
    result.retcode = 10009
    result.price = 3350.05

    with (
        patch(
            "packages.execution.mt5.mt5.terminal_info",
            return_value=MagicMock(),
        ),
        patch(
            "packages.execution.mt5.mt5.symbol_info",
            return_value=info,
        ),
        patch(
            "packages.execution.mt5.mt5.symbol_info_tick",
            return_value=tick,
        ),
        patch(
            "packages.execution.mt5.mt5.order_send",
            return_value=result,
        ) as order_send,
    ):
        provider._connected = True

        submitted = await provider.submit_order(order)

    request = order_send.call_args.args[0]

    assert request["price"] == 3350.05
    assert submitted.status is OrderStatus.FILLED
    assert submitted.price == Decimal("3350.05")


@pytest.mark.asyncio
async def test_submit_order_rejects_quantity_below_minimum() -> None:
    provider = make_provider()
    order = make_order(quantity=Decimal("0.005"))

    info = make_instrument_info()

    with (
        patch(
            "packages.execution.mt5.mt5.terminal_info",
            return_value=MagicMock(),
        ),
        patch(
            "packages.execution.mt5.mt5.symbol_info",
            return_value=info,
        ),
    ):
        provider._connected = True

        with pytest.raises(
            ValueError,
            match="below minimum volume",
        ):
            await provider.submit_order(order)


@pytest.mark.asyncio
async def test_submit_order_rejects_quantity_above_maximum() -> None:
    provider = make_provider()
    order = make_order(quantity=Decimal("100.01"))

    info = make_instrument_info()

    with (
        patch(
            "packages.execution.mt5.mt5.terminal_info",
            return_value=MagicMock(),
        ),
        patch(
            "packages.execution.mt5.mt5.symbol_info",
            return_value=info,
        ),
    ):
        provider._connected = True

        with pytest.raises(
            ValueError,
            match="exceeds maximum volume",
        ):
            await provider.submit_order(order)


@pytest.mark.asyncio
async def test_submit_order_rejects_missing_tick() -> None:
    provider = make_provider()
    order = make_order()

    info = make_instrument_info()

    with (
        patch(
            "packages.execution.mt5.mt5.terminal_info",
            return_value=MagicMock(),
        ),
        patch(
            "packages.execution.mt5.mt5.symbol_info",
            return_value=info,
        ),
        patch(
            "packages.execution.mt5.mt5.symbol_info_tick",
            return_value=None,
        ),
    ):
        provider._connected = True

        with pytest.raises(
            RuntimeError,
            match="Unable to retrieve tick data",
        ):
            await provider.submit_order(order)


@pytest.mark.asyncio
async def test_submit_order_handles_none_order_send_result() -> None:
    provider = make_provider()
    order = make_order()

    info = make_instrument_info()

    tick = MagicMock()
    tick.ask = 3350.25
    tick.bid = 3350.05

    with (
        patch(
            "packages.execution.mt5.mt5.terminal_info",
            return_value=MagicMock(),
        ),
        patch(
            "packages.execution.mt5.mt5.symbol_info",
            return_value=info,
        ),
        patch(
            "packages.execution.mt5.mt5.symbol_info_tick",
            return_value=tick,
        ),
        patch(
            "packages.execution.mt5.mt5.order_send",
            return_value=None,
        ),
        patch(
            "packages.execution.mt5.mt5.last_error",
            return_value=(100, "Order send failed"),
        ),
    ):
        provider._connected = True

        with pytest.raises(
            RuntimeError,
            match="MT5 order submission failed",
        ):
            await provider.submit_order(order)