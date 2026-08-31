from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from packages.core.enums import OrderSide
from packages.core.models import Position
from packages.portfolio.reconciliation import (
    PortfolioReconciliationService,
)
from packages.portfolio.service import PortfolioService


def make_position(
    symbol: str = "XAUUSD",
    quantity: Decimal = Decimal("0.10"),
    entry_price: Decimal = Decimal(3350),
    current_price: Decimal = Decimal(3355),
    unrealized_pnl: Decimal = Decimal(50),
) -> Position:
    from datetime import UTC, datetime

    now = datetime.now(UTC)

    return Position(
        symbol=symbol,
        side=OrderSide.BUY,
        quantity=quantity,
        entry_price=entry_price,
        current_price=current_price,
        opened_at=now,
        unrealized_pnl=unrealized_pnl,
    )


def make_service(
    *,
    balance: Decimal = Decimal(10000),
    positions: list[Position] | None = None,
) -> tuple[
    PortfolioReconciliationService,
    AsyncMock,
    PortfolioService,
]:
    provider = AsyncMock()

    provider.get_account_balance.return_value = float(balance)

    broker_positions = positions or []

    async def get_position(symbol: str) -> Position | None:
        for position in broker_positions:
            if position.symbol == symbol:
                return position
        return None

    provider.get_position.side_effect = get_position

    portfolio = PortfolioService(balance=Decimal(10000))

    service = PortfolioReconciliationService(
        provider=provider,
        portfolio=portfolio,
    )

    return service, provider, portfolio


@pytest.mark.asyncio
async def test_reconcile_updates_balance() -> None:
    service, provider, portfolio = make_service(
        balance=Decimal(12500),
    )

    snapshot = await service.reconcile(["XAUUSD"])

    provider.get_account_balance.assert_awaited_once()

    assert snapshot.balance == Decimal(12500)
    assert portfolio.snapshot().balance == Decimal(12500)


@pytest.mark.asyncio
async def test_reconcile_imports_broker_position() -> None:
    position = make_position()

    service, provider, portfolio = make_service(
        positions=[position],
    )

    snapshot = await service.reconcile(["XAUUSD"])

    provider.get_position.assert_awaited_once_with("XAUUSD")

    assert portfolio.get_position("XAUUSD") == position
    assert snapshot.open_positions == 1


@pytest.mark.asyncio
async def test_reconcile_updates_existing_position() -> None:
    service, _, portfolio = make_service(
        positions=[
            make_position(
                quantity=Decimal("0.20"),
                entry_price=Decimal(3350),
                current_price=Decimal(3360),
                unrealized_pnl=Decimal(100),
            )
        ],
    )

    local_position = make_position(
        quantity=Decimal("0.10"),
        entry_price=Decimal(3300),
        current_price=Decimal(3300),
        unrealized_pnl=Decimal(0),
    )

    portfolio.add_position(local_position)

    snapshot = await service.reconcile(["XAUUSD"])

    position = portfolio.get_position("XAUUSD")

    assert position is not None
    assert position.quantity == Decimal("0.20")
    assert position.entry_price == Decimal(3350)
    assert position.current_price == Decimal(3360)
    assert position.unrealized_pnl == Decimal(100)
    assert snapshot.open_positions == 1


@pytest.mark.asyncio
async def test_reconcile_removes_local_position_missing_from_broker() -> None:
    service, _, portfolio = make_service()

    portfolio.add_position(make_position())

    snapshot = await service.reconcile(["XAUUSD"])

    assert portfolio.get_position("XAUUSD") is None
    assert snapshot.open_positions == 0


@pytest.mark.asyncio
async def test_reconcile_supports_multiple_symbols() -> None:
    xau = make_position("XAUUSD")
    eur = make_position(
        symbol="EURUSD",
        entry_price=Decimal("1.10"),
        current_price=Decimal("1.11"),
    )

    service, provider, portfolio = make_service(
        positions=[xau, eur],
    )

    snapshot = await service.reconcile(
        ["XAUUSD", "EURUSD"],
    )

    assert provider.get_position.await_count == 2
    assert portfolio.get_position("XAUUSD") == xau
    assert portfolio.get_position("EURUSD") == eur
    assert snapshot.open_positions == 2


@pytest.mark.asyncio
async def test_reconcile_clears_stale_positions() -> None:
    service, _, portfolio = make_service()

    portfolio.add_position(
        make_position("XAUUSD")
    )
    portfolio.add_position(
        make_position("EURUSD")
    )

    snapshot = await service.reconcile(["XAUUSD"])

    assert portfolio.get_position("XAUUSD") is None
    assert portfolio.get_position("EURUSD") is None
    assert snapshot.open_positions == 0


@pytest.mark.asyncio
async def test_reconcile_propagates_balance_error() -> None:
    service, provider, _ = make_service()

    provider.get_account_balance.side_effect = RuntimeError(
        "Account unavailable"
    )

    with pytest.raises(
        RuntimeError,
        match="Account unavailable",
    ):
        await service.reconcile(["XAUUSD"])


@pytest.mark.asyncio
async def test_reconcile_propagates_position_error() -> None:
    service, provider, _ = make_service()

    provider.get_position.side_effect = RuntimeError(
        "Position service unavailable"
    )

    with pytest.raises(
        RuntimeError,
        match="Position service unavailable",
    ):
        await service.reconcile(["XAUUSD"])