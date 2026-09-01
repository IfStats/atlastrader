
from decimal import Decimal
from unittest.mock import MagicMock, patch

import MetaTrader5 as mt5  # type: ignore[import-untyped]
import pytest

from packages.core.enums import AssetClass, OrderSide, OrderStatus, OrderType
from packages.core.models import Order
from packages.execution.mt5 import MT5ExecutionProvider


def make_provider() -> MT5ExecutionProvider:
    return MT5ExecutionProvider(
        login=123456,
        password="test-password",
        server="Test-Server",
    )


def make_order() -> Order:
    return Order(
        id="test-order-001",
        symbol="XAUUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        status=OrderStatus.PENDING,
        quantity=Decimal("0.01"),
        stop_loss=Decimal(3345),
        take_profit=Decimal(3360),
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )


@pytest.mark.asyncio
async def test_connect_initializes_mt5() -> None:
    provider = make_provider()

    with patch(
        "packages.execution.mt5.mt5.initialize",
        return_value=True,
    ) as initialize:
        await provider.connect()

    initialize.assert_called_once_with(
        login=123456,
        password="test-password",
        server="Test-Server",
    )


@pytest.mark.asyncio
async def test_connect_raises_when_mt5_initialization_fails() -> None:
    provider = make_provider()

    with (
        patch(
            "packages.execution.mt5.mt5.initialize",
            return_value=False,
        ),
        patch(
            "packages.execution.mt5.mt5.last_error",
            return_value=(1, "Initialization failed"),
        ),
        pytest.raises(RuntimeError, match="Failed to initialize"),
    ):
        await provider.connect()


@pytest.mark.asyncio
async def test_disconnect_shuts_down_mt5() -> None:
    provider = make_provider()
    provider._connected = True

    with patch("packages.execution.mt5.mt5.shutdown") as shutdown:
        await provider.disconnect()

    shutdown.assert_called_once()
    assert await provider.is_connected() is False


@pytest.mark.asyncio
async def test_is_connected_returns_false_when_not_connected() -> None:
    provider = make_provider()

    assert await provider.is_connected() is False


@pytest.mark.asyncio
async def test_get_account_balance_returns_balance() -> None:
    provider = make_provider()

    account = MagicMock()
    account.balance = 10000.50

    with (
        patch(
            "packages.execution.mt5.mt5.terminal_info",
            return_value=MagicMock(),
        ),
        patch(
            "packages.execution.mt5.mt5.account_info",
            return_value=account,
        ),
    ):
        provider._connected = True
        balance = await provider.get_account_balance()

    assert balance == 10000.50


@pytest.mark.asyncio
async def test_get_account_balance_requires_connection() -> None:
    provider = make_provider()

    with pytest.raises(
        RuntimeError,
        match="MetaTrader 5 is not connected",
    ):
        await provider.get_account_balance()


@pytest.mark.asyncio
async def test_get_instrument_raises_when_symbol_is_missing() -> None:
    provider = make_provider()

    with (
        patch(
            "packages.execution.mt5.mt5.terminal_info",
            return_value=MagicMock(),
        ),
        patch(
            "packages.execution.mt5.mt5.symbol_info",
            return_value=None,
        ),
    ):
        provider._connected = True

        with pytest.raises(
            KeyError,
            match="Instrument not found",
        ):
            await provider.get_instrument("XAUUSD")


@pytest.mark.asyncio
async def test_get_instrument_maps_mt5_metadata() -> None:
    provider = make_provider()

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
        instrument = await provider.get_instrument("XAUUSD")

    assert instrument.symbol == "XAUUSD"
    assert instrument.name == "XAUUSD"
    assert instrument.asset_class is AssetClass.METAL
    assert instrument.tick_size == Decimal("0.01")
    assert instrument.contract_size == Decimal("100.0")
    assert instrument.min_volume == Decimal("0.01")
    assert instrument.volume_step == Decimal("0.01")
    assert instrument.price_precision == 2
    assert instrument.volume_precision == 2
    assert instrument.enabled is True


@pytest.mark.asyncio
async def test_submit_order_requires_connection() -> None:
    provider = make_provider()
    order = make_order()

    with pytest.raises(
        RuntimeError,
        match="MetaTrader 5 is not connected",
    ):
        await provider.submit_order(order)


@pytest.mark.asyncio
async def test_submit_order_rejects_non_market_orders() -> None:
    provider = make_provider()

    order = make_order().model_copy(
        update={"order_type": OrderType.LIMIT}
    )

    with (
        patch(
            "packages.execution.mt5.mt5.terminal_info",
            return_value=MagicMock(),
        ),
        pytest.raises(
            ValueError,
            match="market orders only",
        ),
    ):
        provider._connected = True
        await provider.submit_order(order)


@pytest.mark.asyncio
async def test_submit_order_rejects_mt5_error() -> None:
    provider = make_provider()
    order = make_order()

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

    tick = MagicMock()
    tick.ask = 3350.25
    tick.bid = 3350.05

    result = MagicMock()
    result.retcode = 10016
    result.comment = "Invalid stops"

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
        ),
    ):
        provider._connected = True

        with pytest.raises(
            RuntimeError,
            match="MT5 order rejected",
        ):
            await provider.submit_order(order)


@pytest.mark.asyncio
async def test_get_position_returns_none_when_no_position_exists() -> None:
    provider = make_provider()

    with (
        patch(
            "packages.execution.mt5.mt5.terminal_info",
            return_value=MagicMock(),
        ),
        patch(
            "packages.execution.mt5.mt5.positions_get",
            return_value=[],
        ),
    ):
        provider._connected = True
        position = await provider.get_position("XAUUSD")

    assert position is None

@pytest.mark.asyncio
async def test_submit_order_rejects_quantity_not_aligned_to_volume_step() -> None:
    provider = make_provider()

    order = make_order().model_copy(
        update={"quantity": Decimal("0.015")}
    )

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
            match="aligned with volume step",
        ):
            await provider.submit_order(order)


@pytest.mark.asyncio
async def test_submit_order_accepts_quantity_aligned_to_volume_step() -> None:
    provider = make_provider()
    order = make_order()

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

    tick = MagicMock()
    tick.ask = 3350.25
    tick.bid = 3350.05

    result = MagicMock()
    result.retcode = mt5.TRADE_RETCODE_DONE
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
        ),
    ):
        provider._connected = True
        submitted = await provider.submit_order(order)

    assert submitted.status is OrderStatus.FILLED

@pytest.mark.asyncio
async def test_submit_order_continues_when_no_existing_position() -> None:
    provider = make_provider()
    order = make_order()

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
    info.currency_profit = "USD"
    info.filling_mode = 0

    tick = MagicMock()
    tick.ask = 3350.25
    tick.bid = 3350.05

    result = MagicMock()
    result.retcode = mt5.TRADE_RETCODE_DONE
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
            "packages.execution.mt5.mt5.positions_get",
            return_value=[],
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

    assert submitted.status is OrderStatus.FILLED
    order_send.assert_called_once()