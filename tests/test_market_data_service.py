import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from packages.core.enums import Timeframe
from packages.core.models import Candle, Quote
from packages.market_data.base import MarketDataProvider
from packages.market_data.cache import MarketDataCache
from packages.market_data.service import MarketDataService


def make_provider() -> AsyncMock:
    return AsyncMock(spec=MarketDataProvider)


def make_candles(
    *,
    symbol: str = "XAUUSD",
    timeframe: Timeframe = Timeframe.M5,
) -> list[Candle]:
    base_time = datetime.now(UTC) - timedelta(minutes=20)

    return [
        Candle(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=base_time,
            open=Decimal(3340),
            high=Decimal(3346),
            low=Decimal(3338),
            close=Decimal(3345),
            volume=Decimal(1000),
        ),
        Candle(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=base_time + timedelta(minutes=5),
            open=Decimal(3345),
            high=Decimal(3351),
            low=Decimal(3343),
            close=Decimal(3350),
            volume=Decimal(1100),
        ),
        Candle(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=base_time + timedelta(minutes=10),
            open=Decimal(3350),
            high=Decimal(3357),
            low=Decimal(3348),
            close=Decimal(3355),
            volume=Decimal(1200),
        ),
    ]


@pytest.mark.asyncio
async def test_get_market_state_normalizes_quote_and_indicators() -> None:
    provider = make_provider()

    timestamp = datetime.now(UTC)

    provider.get_quote.return_value = Quote(
        symbol="XAUUSD",
        bid=Decimal("3350.25"),
        ask=Decimal("3350.45"),
        timestamp=timestamp,
    )

    provider.get_candles.return_value = make_candles()

    service = MarketDataService(
        provider,
        timeframe=Timeframe.M5,
    )

    state = await service.get_market_state("XAUUSD")

    assert state.symbol == "XAUUSD"
    assert state.timeframe is Timeframe.M5
    assert state.price == Decimal("3350.35")
    assert state.spread == Decimal("0.20")

    assert state.trend_score > 0
    assert state.momentum_score > 0
    assert state.volatility_score > 0
    assert state.volatility > Decimal(0)

    assert state.is_tradeable is True

    provider.get_quote.assert_awaited_once_with("XAUUSD")
    provider.get_candles.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_market_state_uses_configured_timeframe() -> None:
    provider = make_provider()

    timestamp = datetime.now(UTC)

    provider.get_quote.return_value = Quote(
        symbol="EURUSD",
        bid=Decimal("1.1000"),
        ask=Decimal("1.1002"),
        timestamp=timestamp,
    )

    provider.get_candles.return_value = make_candles(
        symbol="EURUSD",
        timeframe=Timeframe.M1,
    )

    service = MarketDataService(
        provider,
        timeframe=Timeframe.M1,
    )

    state = await service.get_market_state("EURUSD")

    assert state.symbol == "EURUSD"
    assert state.timeframe is Timeframe.M1
    assert state.price == Decimal("1.1001")

    provider.get_candles.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_market_state_requests_configured_candle_lookback() -> None:
    provider = make_provider()

    timestamp = datetime.now(UTC)

    provider.get_quote.return_value = Quote(
        symbol="XAUUSD",
        bid=Decimal("3350.25"),
        ask=Decimal("3350.45"),
        timestamp=timestamp,
    )

    provider.get_candles.return_value = make_candles()

    service = MarketDataService(
        provider,
        timeframe=Timeframe.M5,
        candle_lookback=20,
    )

    await service.get_market_state("XAUUSD")

    provider.get_candles.assert_awaited_once()

    call = provider.get_candles.await_args

    assert call.args[0] == "XAUUSD"
    assert call.args[1] is Timeframe.M5
    assert call.args[2] < call.args[3]


@pytest.mark.asyncio
async def test_get_market_state_propagates_provider_error() -> None:
    provider = make_provider()

    provider.get_quote.side_effect = RuntimeError(
        "market data unavailable"
    )

    service = MarketDataService(provider)

    with pytest.raises(
        RuntimeError,
        match="market data unavailable",
    ):
        await service.get_market_state("XAUUSD")

    provider.get_quote.assert_awaited_once_with("XAUUSD")


def test_market_data_service_rejects_invalid_lookback() -> None:
    provider = make_provider()

    with pytest.raises(
        ValueError,
        match="candle_lookback must be at least 2",
    ):
        MarketDataService(
            provider,
            candle_lookback=1,
        )


@pytest.mark.asyncio
async def test_get_market_state_calculates_expected_indicators() -> None:
    provider = make_provider()

    timestamp = datetime(2026, 8, 15, 15, 0, tzinfo=UTC)

    provider.get_quote.return_value = Quote(
        symbol="XAUUSD",
        bid=Decimal("3350.25"),
        ask=Decimal("3350.45"),
        timestamp=timestamp,
    )

    candles = [
        Candle(
            symbol="XAUUSD",
            timeframe=Timeframe.M5,
            timestamp=timestamp - timedelta(minutes=15),
            open=Decimal(3340),
            high=Decimal(3346),
            low=Decimal(3338),
            close=Decimal(3345),
            volume=Decimal(1000),
        ),
        Candle(
            symbol="XAUUSD",
            timeframe=Timeframe.M5,
            timestamp=timestamp - timedelta(minutes=10),
            open=Decimal(3345),
            high=Decimal(3351),
            low=Decimal(3343),
            close=Decimal(3350),
            volume=Decimal(1100),
        ),
        Candle(
            symbol="XAUUSD",
            timeframe=Timeframe.M5,
            timestamp=timestamp - timedelta(minutes=5),
            open=Decimal(3350),
            high=Decimal(3357),
            low=Decimal(3348),
            close=Decimal(3355),
            volume=Decimal(1200),
        ),
    ]

    provider.get_candles.return_value = candles

    service = MarketDataService(
        provider,
        timeframe=Timeframe.M5,
        candle_lookback=20,
    )

    state = await service.get_market_state("XAUUSD")

    assert state.trend_score == pytest.approx(
        0.0298953662,
        rel=1e-5,
    )
    assert state.momentum_score == pytest.approx(
        0.1492537,
        rel=1e-5,
    )
    assert state.volatility_score == pytest.approx(
        0.2487562,
        rel=1e-3,
    )
    assert state.volatility == (
        Decimal(8) + Decimal(8) + Decimal(9)
    ) / Decimal(3)


@pytest.mark.asyncio
async def test_get_market_state_requests_exact_candle_window() -> None:
    provider = make_provider()

    timestamp = datetime(2026, 8, 15, 15, 0, tzinfo=UTC)

    provider.get_quote.return_value = Quote(
        symbol="XAUUSD",
        bid=Decimal("3350.25"),
        ask=Decimal("3350.45"),
        timestamp=timestamp,
    )

    provider.get_candles.return_value = make_candles()

    service = MarketDataService(
        provider,
        timeframe=Timeframe.M5,
        candle_lookback=20,
    )

    await service.get_market_state("XAUUSD")

    provider.get_candles.assert_awaited_once_with(
        "XAUUSD",
        Timeframe.M5,
        timestamp - timedelta(minutes=100),
        timestamp,
    )

@pytest.mark.asyncio
async def test_get_market_state_uses_cached_quote_and_candles() -> None:
    provider = make_provider()

    timestamp = datetime.now(UTC)

    quote = Quote(
        symbol="XAUUSD",
        bid=Decimal("3350.25"),
        ask=Decimal("3350.45"),
        timestamp=timestamp,
    )

    candles = make_candles()

    provider.get_quote.return_value = quote
    provider.get_candles.return_value = candles

    cache = MarketDataCache(
        quote_ttl=timedelta(minutes=1),
        candle_ttl=timedelta(minutes=1),
    )

    service = MarketDataService(
        provider,
        timeframe=Timeframe.M5,
        cache=cache,
    )

    first_state = await service.get_market_state("XAUUSD")
    second_state = await service.get_market_state("XAUUSD")

    assert first_state == second_state

    provider.get_quote.assert_awaited_once_with("XAUUSD")
    provider.get_candles.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_market_state_refreshes_expired_quote() -> None:
    provider = make_provider()

    timestamp = datetime.now(UTC)

    provider.get_quote.return_value = Quote(
        symbol="XAUUSD",
        bid=Decimal("3350.25"),
        ask=Decimal("3350.45"),
        timestamp=timestamp,
    )

    provider.get_candles.return_value = make_candles()

    cache = MarketDataCache(
        quote_ttl=timedelta(0, microseconds=1),
        candle_ttl=timedelta(minutes=1),
    )

    service = MarketDataService(
        provider,
        timeframe=Timeframe.M5,
        cache=cache,
    )

    await service.get_market_state("XAUUSD")

    await asyncio.sleep(0.001)

    await service.get_market_state("XAUUSD")

    assert provider.get_quote.await_count == 2

