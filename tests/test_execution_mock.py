from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.core.enums import OrderSide
from packages.core.models import Position
from packages.execution.mock import MockExecutionProvider


def make_position(symbol: str) -> Position:
    return Position(
        symbol=symbol,
        side=OrderSide.BUY,
        quantity=Decimal("0.10"),
        entry_price=Decimal(3300),
        current_price=Decimal(3300),
        opened_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_mock_execution_returns_all_open_positions() -> None:
    provider = MockExecutionProvider()

    xau = make_position("XAUUSD")
    eur = make_position("EURUSD")

    provider.add_position(xau)
    provider.add_position(eur)

    positions = await provider.get_positions()

    assert positions == [xau, eur]