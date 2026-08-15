from datetime import UTC, datetime

import pytest

from packages.market_data.mock import MockMarketDataProvider


@pytest.mark.asyncio
async def test_mock_quote() -> None:
    provider = MockMarketDataProvider()

    quote = await provider.get_quote("XAUUSD")

    assert quote.symbol == "XAUUSD"
    assert quote.bid < quote.ask
    assert quote.spread > 0


@pytest.mark.asyncio
async def test_mock_candles() -> None:
    provider = MockMarketDataProvider()

    start = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    end = datetime(2026, 8, 15, 11, 0, tzinfo=UTC)

    candles = await provider.get_candles(
        symbol="XAUUSD",
        timeframe="5m",
        start=start,
        end=end,
    )

    assert len(candles) == 1
    assert candles[0].symbol == "XAUUSD"
    assert candles[0].close > candles[0].open