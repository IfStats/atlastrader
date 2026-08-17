from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.core.enums import OrderSide, PositionStatus
from packages.core.models import Position
from packages.portfolio.models import PortfolioSnapshot
from packages.portfolio.service import PortfolioService

NOW = datetime.now(UTC)


def make_position(
    symbol: str = "XAUUSD",
    quantity: Decimal = Decimal("0.10"),
    entry_price: Decimal = Decimal(2000),
    unrealized_pnl: Decimal = Decimal(25),
    realized_pnl: Decimal = Decimal(0),
) -> Position:
    return Position(
        symbol=symbol,
        side=OrderSide.BUY,
        status=PositionStatus.OPEN,
        quantity=quantity,
        entry_price=entry_price,
        current_price=entry_price,
        opened_at=NOW,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
    )


def test_empty_portfolio_snapshot() -> None:
    service = PortfolioService(
        balance=Decimal(10000),
    )

    snapshot = service.snapshot()

    assert isinstance(snapshot, PortfolioSnapshot)
    assert snapshot.balance == Decimal(10000)
    assert snapshot.equity == Decimal(10000)
    assert snapshot.open_positions == 0
    assert snapshot.total_exposure == Decimal(0)
    assert snapshot.net_pnl == Decimal(0)


def test_add_position() -> None:
    service = PortfolioService(
        balance=Decimal(10000),
    )

    position = make_position()

    service.add_position(position)

    assert service.get_position("XAUUSD") == position
    assert len(service.positions()) == 1


def test_replace_position() -> None:
    service = PortfolioService(
        balance=Decimal(10000),
    )

    first = make_position(
        quantity=Decimal("0.10"),
    )

    second = make_position(
        quantity=Decimal("0.20"),
    )

    service.add_position(first)
    service.add_position(second)

    assert len(service.positions()) == 1
    assert service.get_position("XAUUSD") == second


def test_remove_position() -> None:
    service = PortfolioService(
        balance=Decimal(10000),
    )

    service.add_position(make_position())

    service.remove_position("XAUUSD")

    assert service.get_position("XAUUSD") is None
    assert service.positions() == []


def test_snapshot_calculates_pnl_and_exposure() -> None:
    service = PortfolioService(
        balance=Decimal(10000),
    )

    service.add_position(
        make_position(
            quantity=Decimal("0.10"),
            entry_price=Decimal(2000),
            unrealized_pnl=Decimal(25),
            realized_pnl=Decimal(10),
        )
    )

    snapshot = service.snapshot()

    assert snapshot.realized_pnl == Decimal(10)
    assert snapshot.unrealized_pnl == Decimal(25)
    assert snapshot.net_pnl == Decimal(35)
    assert snapshot.equity == Decimal(10035)
    assert snapshot.total_exposure == Decimal(200)


def test_available_equity() -> None:
    service = PortfolioService(
        balance=Decimal(10000),
    )

    service.add_position(
        make_position(
            quantity=Decimal("0.10"),
            entry_price=Decimal(2000),
        )
    )

    snapshot = service.snapshot()

    assert snapshot.available_equity == Decimal(9825)


def test_negative_balance_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="balance must be greater than or equal to zero",
    ):
        PortfolioService(
            balance=Decimal(-1),
        )

def test_update_position_changes_price_and_unrealized_pnl() -> None:
    service = PortfolioService(
        balance=Decimal(10000),
    )

    service.add_position(make_position())

    updated = service.update_position(
        "XAUUSD",
        current_price=Decimal(2010),
        unrealized_pnl=Decimal(50),
    )

    assert updated.current_price == Decimal(2010)
    assert updated.unrealized_pnl == Decimal(50)

    snapshot = service.snapshot()

    assert snapshot.unrealized_pnl == Decimal(50)
    assert snapshot.equity == Decimal(10050)


def test_close_position_records_realized_pnl() -> None:
    service = PortfolioService(
        balance=Decimal(10000),
    )

    service.add_position(make_position())

    closed = service.close_position(
        "XAUUSD",
        current_price=Decimal(2020),
        realized_pnl=Decimal(100),
    )

    assert closed.status is PositionStatus.CLOSED
    assert closed.current_price == Decimal(2020)
    assert closed.realized_pnl == Decimal(100)
    assert closed.unrealized_pnl == Decimal(0)
    assert closed.closed_at is not None

    assert service.get_position("XAUUSD") is None

    snapshot = service.snapshot()

    assert snapshot.open_positions == 0
    assert snapshot.realized_pnl == Decimal(100)
    assert snapshot.unrealized_pnl == Decimal(0)
    assert snapshot.net_pnl == Decimal(100)
    assert snapshot.equity == Decimal(10100)


def test_update_missing_position_is_rejected() -> None:
    service = PortfolioService(
        balance=Decimal(10000),
    )

    with pytest.raises(
        KeyError,
        match="Position not found: XAUUSD",
    ):
        service.update_position(
            "XAUUSD",
            current_price=Decimal(2000),
            unrealized_pnl=Decimal(10),
        )


def test_close_missing_position_is_rejected() -> None:
    service = PortfolioService(
        balance=Decimal(10000),
    )

    with pytest.raises(
        KeyError,
        match="Position not found: XAUUSD",
    ):
        service.close_position(
            "XAUUSD",
            current_price=Decimal(2000),
            realized_pnl=Decimal(10),
        )

def test_mark_long_position_calculates_unrealized_pnl() -> None:
    service = PortfolioService(
        balance=Decimal(10000),
    )

    service.add_position(
        make_position(
            quantity=Decimal("0.10"),
            entry_price=Decimal(2000),
        )
    )

    position = service.mark_position(
        "XAUUSD",
        current_price=Decimal(2010),
        contract_size=Decimal(100),
    )

    assert position.current_price == Decimal(2010)
    assert position.unrealized_pnl == Decimal(100)

    snapshot = service.snapshot()

    assert snapshot.unrealized_pnl == Decimal(100)
    assert snapshot.equity == Decimal(10100)


def test_mark_short_position_calculates_unrealized_pnl() -> None:
    service = PortfolioService(
        balance=Decimal(10000),
    )

    position = make_position(
        quantity=Decimal("0.10"),
        entry_price=Decimal(2000),
    ).model_copy(
        update={"side": OrderSide.SELL}
    )

    service.add_position(position)

    updated = service.mark_position(
        "XAUUSD",
        current_price=Decimal(1990),
        contract_size=Decimal(100),
    )

    assert updated.unrealized_pnl == Decimal(100)


def test_mark_position_rejects_invalid_current_price() -> None:
    service = PortfolioService(
        balance=Decimal(10000),
    )

    service.add_position(make_position())

    with pytest.raises(
        ValueError,
        match="current_price must be greater than zero",
    ):
        service.mark_position(
            "XAUUSD",
            current_price=Decimal(0),
            contract_size=Decimal(100),
        )


def test_mark_position_rejects_invalid_contract_size() -> None:
    service = PortfolioService(
        balance=Decimal(10000),
    )

    service.add_position(make_position())

    with pytest.raises(
        ValueError,
        match="contract_size must be greater than zero",
    ):
        service.mark_position(
            "XAUUSD",
            current_price=Decimal(2010),
            contract_size=Decimal(0),
        )


def test_position_lifecycle_mark_then_close() -> None:
    service = PortfolioService(
        balance=Decimal(10000),
    )

    service.add_position(
        make_position(
            quantity=Decimal("0.10"),
            entry_price=Decimal(2000),
        )
    )

    marked = service.mark_position(
        "XAUUSD",
        current_price=Decimal(2010),
        contract_size=Decimal(100),
    )

    assert marked.unrealized_pnl == Decimal(100)

    snapshot = service.snapshot()

    assert snapshot.unrealized_pnl == Decimal(100)
    assert snapshot.equity == Decimal(10100)

    closed = service.close_position(
        "XAUUSD",
        current_price=Decimal(2010),
        realized_pnl=Decimal(100),
    )

    assert closed.status is PositionStatus.CLOSED

    final_snapshot = service.snapshot()

    assert final_snapshot.open_positions == 0
    assert final_snapshot.realized_pnl == Decimal(100)
    assert final_snapshot.unrealized_pnl == Decimal(0)
    assert final_snapshot.net_pnl == Decimal(100)
    assert final_snapshot.equity == Decimal(10100)

def test_update_closed_position_is_rejected() -> None:
    service = PortfolioService(
        balance=Decimal(10000),
    )

    service.add_position(make_position())

    service.close_position(
        "XAUUSD",
        current_price=Decimal(2020),
        realized_pnl=Decimal(100),
    )

    with pytest.raises(
        KeyError,
        match="Position not found: XAUUSD",
    ):
        service.update_position(
            "XAUUSD",
            current_price=Decimal(2025),
            unrealized_pnl=Decimal(50),
        )

def test_snapshot_aggregates_multiple_positions() -> None:
    service = PortfolioService(
        balance=Decimal(10000),
    )

    service.add_position(
        make_position(
            symbol="XAUUSD",
            quantity=Decimal("0.10"),
            entry_price=Decimal(2000),
            unrealized_pnl=Decimal(100),
        )
    )

    service.add_position(
        make_position(
            symbol="EURUSD",
            quantity=Decimal("1.00"),
            entry_price=Decimal("1.10"),
            unrealized_pnl=Decimal(50),
        )
    )

    snapshot = service.snapshot()

    assert snapshot.open_positions == 2
    assert snapshot.unrealized_pnl == Decimal(150)
    assert snapshot.total_exposure == Decimal("201.10")
    assert snapshot.equity == Decimal(10150)