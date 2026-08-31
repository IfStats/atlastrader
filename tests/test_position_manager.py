from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from packages.core.enums import OrderSide, OrderStatus, OrderType
from packages.core.models import Order, Position
from packages.portfolio.position_manager import PositionManager
from packages.portfolio.service import PortfolioService


def make_position(
    symbol: str = "XAUUSD",
    quantity: Decimal = Decimal("0.10"),
    entry_price: Decimal = Decimal(3350),
) -> Position:
    from datetime import UTC, datetime

    now = datetime.now(UTC)

    return Position(
        symbol=symbol,
        side=OrderSide.BUY,
        quantity=quantity,
        entry_price=entry_price,
        current_price=entry_price,
        opened_at=now,
    )


def make_manager(
    positions: list[Position] | None = None,
    balance: float = 10000,
) -> tuple[PositionManager, AsyncMock, PortfolioService]:
    provider = AsyncMock()

    provider.get_positions.return_value = positions or []
    provider.get_account_balance.return_value = balance

    portfolio = PortfolioService(
        balance=Decimal(10000),
    )

    manager = PositionManager(
        execution_provider=provider,
        portfolio=portfolio,
    )

    return manager, provider, portfolio


@pytest.mark.asyncio
async def test_sync_imports_broker_positions() -> None:
    position = make_position()

    manager, provider, portfolio = make_manager(
        positions=[position],
    )

    result = await manager.sync()

    provider.get_positions.assert_awaited_once()

    assert result == [position]
    assert portfolio.get_position("XAUUSD") == position


@pytest.mark.asyncio
async def test_sync_removes_positions_missing_from_broker() -> None:
    manager, provider, portfolio = make_manager()

    existing = make_position()

    portfolio.add_position(existing)

    provider.get_positions.return_value = []

    result = await manager.sync()

    assert result == []
    assert portfolio.get_position("XAUUSD") is None


@pytest.mark.asyncio
async def test_sync_replaces_existing_position_with_broker_state() -> None:
    manager, provider, portfolio = make_manager()

    existing = make_position(
        quantity=Decimal("0.10"),
        entry_price=Decimal(3300),
    )

    broker_position = make_position(
        quantity=Decimal("0.20"),
        entry_price=Decimal(3350),
    )

    portfolio.add_position(existing)
    provider.get_positions.return_value = [broker_position]

    result = await manager.sync()

    assert result == [broker_position]
    assert portfolio.get_position("XAUUSD") == broker_position


@pytest.mark.asyncio
async def test_sync_supports_multiple_symbols() -> None:
    xau = make_position(
        symbol="XAUUSD",
    )

    eur = make_position(
        symbol="EURUSD",
        entry_price=Decimal("1.10"),
    )

    manager, _provider, portfolio = make_manager(
        positions=[xau, eur],
    )

    result = await manager.sync()

    assert result == [xau, eur]
    assert portfolio.get_position("XAUUSD") == xau
    assert portfolio.get_position("EURUSD") == eur


@pytest.mark.asyncio
async def test_sync_propagates_provider_error() -> None:
    manager, provider, _ = make_manager()

    provider.get_positions.side_effect = RuntimeError(
        "Unable to retrieve positions"
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to retrieve positions",
    ):
        await manager.sync()


@pytest.mark.asyncio
async def test_sync_balance_updates_portfolio_balance() -> None:
    manager, provider, portfolio = make_manager(
        balance=12500,
    )

    result = await manager.sync_balance()

    provider.get_account_balance.assert_awaited_once()

    assert result == Decimal(12500)
    assert portfolio.snapshot().balance == Decimal(12500)


@pytest.mark.asyncio
async def test_sync_balance_converts_broker_balance_to_decimal() -> None:
    manager, _provider, portfolio = make_manager(
        balance=12345.67,
    )

    result = await manager.sync_balance()

    assert result == Decimal("12345.67")
    assert portfolio.snapshot().balance == Decimal("12345.67")


@pytest.mark.asyncio
async def test_sync_balance_propagates_provider_error() -> None:
    manager, provider, _ = make_manager()

    provider.get_account_balance.side_effect = RuntimeError(
        "Account unavailable"
    )

    with pytest.raises(
        RuntimeError,
        match="Account unavailable",
    ):
        await manager.sync_balance()


@pytest.mark.asyncio
async def test_sync_all_updates_balance_and_positions() -> None:
    position = make_position()

    manager, provider, portfolio = make_manager(
        positions=[position],
        balance=15000,
    )

    result = await manager.sync_all()

    provider.get_account_balance.assert_awaited_once()
    provider.get_positions.assert_awaited_once()

    assert result == [position]
    assert portfolio.snapshot().balance == Decimal(15000)
    assert portfolio.get_position("XAUUSD") == position

@pytest.mark.asyncio
async def test_record_filled_order_creates_portfolio_position() -> None:
    manager, _, portfolio = make_manager()

    from datetime import UTC, datetime


    now = datetime.now(UTC)

    order = Order(
        id="test-order",
        symbol="XAUUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        status=OrderStatus.FILLED,
        quantity=Decimal("0.20"),
        price=Decimal(3350),
        stop_loss=Decimal(3345),
        take_profit=Decimal(3360),
        created_at=now,
        updated_at=now,
    )

    position = manager.record_filled_order(order)

    assert position.symbol == "XAUUSD"
    assert position.side is OrderSide.BUY
    assert position.quantity == Decimal("0.20")
    assert position.entry_price == Decimal(3350)
    assert position.current_price == Decimal(3350)

    assert portfolio.get_position("XAUUSD") == position


@pytest.mark.asyncio
async def test_record_filled_order_requires_fill_price() -> None:
    manager, _, _ = make_manager()

    from datetime import UTC, datetime


    now = datetime.now(UTC)

    order = Order(
        id="test-order",
        symbol="XAUUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        status=OrderStatus.FILLED,
        quantity=Decimal("0.20"),
        price=None,
        created_at=now,
        updated_at=now,
    )

    with pytest.raises(
        ValueError,
        match="Filled order must have a price",
    ):
        manager.record_filled_order(order)