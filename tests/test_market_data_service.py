from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from packages.core.enums import Timeframe
from packages.core.models import Quote
from packages.market_data.base import MarketDataProvider
from packages.market_data.service import MarketDataService


def make_provider() -> AsyncMock:
    return AsyncMock(spec=MarketDataProvider)


@pytest.mark.asyncio
async def test_get_market_state_normalizes_quote() -> None:
    provider = make_provider()

    provider.get_quote.return_value = Quote(
        symbol="XAUUSD",
        bid=Decimal("3350.25"),
        ask=Decimal("3350.45"),
        timestamp=datetime.now(UTC),
    )

    service = MarketDataService(
        provider,
        timeframe=Timeframe.M5,
    )

    state = await service.get_market_state("XAUUSD")

    assert state.symbol == "XAUUSD"
    assert state.timeframe is Timeframe.M5
    assert state.price == Decimal("3350.35")
    assert state.spread == Decimal("0.20")
    assert state.is_tradeable is True

    provider.get_quote.assert_awaited_once_with("XAUUSD")


@pytest.mark.asyncio
async def test_get_market_state_uses_configured_timeframe() -> None:
    provider = make_provider()

    provider.get_quote.return_value = Quote(
        symbol="EURUSD",
        bid=Decimal("1.1000"),
        ask=Decimal("1.1002"),
        timestamp=datetime.now(UTC),
    )

    service = MarketDataService(
        provider,
        timeframe=Timeframe.M1,
    )

    state = await service.get_market_state("EURUSD")

    assert state.symbol == "EURUSD"
    assert state.timeframe is Timeframe.M1
    assert state.price == Decimal("1.1001")


@pytest.mark.asyncio
async def test_get_market_state_propagates_provider_error() -> None:
    provider = make_provider()
    provider.get_quote.side_effect = RuntimeError("market data unavailable")

    service = MarketDataService(provider)

    with pytest.raises(RuntimeError, match="market data unavailable"):
        await service.get_market_state("XAUUSD")

    provider.get_quote.assert_awaited_once_with("XAUUSD")