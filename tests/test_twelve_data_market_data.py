from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from packages.core.enums import Timeframe
from packages.market_data.http import (
    MarketDataHTTPTransport,
)
from packages.market_data.observations import (
    PriceObservationType,
)
from packages.market_data.twelve_data import (
    TwelveDataObservationalProvider,
)


def make_provider(
    transport: AsyncMock,
) -> TwelveDataObservationalProvider:
    return TwelveDataObservationalProvider(
        api_key="test-api-key",
        transport=transport,
    )


@pytest.mark.asyncio
async def test_provider_rejects_empty_api_key() -> None:
    with pytest.raises(
        ValueError,
        match="api_key",
    ):
        TwelveDataObservationalProvider(
            api_key="   "
        )


@pytest.mark.asyncio
async def test_owned_transport_uses_header_auth() -> None:
    provider = TwelveDataObservationalProvider(
        api_key="test-api-key",
    )

    assert (
        provider._transport.headers[
            "Authorization"
        ]
        == "apikey test-api-key"
    )

    await provider.connect()
    assert provider._connected is True

    await provider.disconnect()
    assert provider._connected is False


@pytest.mark.asyncio
async def test_get_observation_requires_connection() -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    provider = make_provider(
        transport
    )

    with pytest.raises(
        RuntimeError,
        match="not connected",
    ):
        await provider.get_observation(
            "XAUUSD"
        )


@pytest.mark.asyncio
async def test_get_observation_normalizes_live_price() -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    transport.get_json.return_value = {
        "price": "4378.15000",
    }

    provider = make_provider(
        transport
    )
    await provider.connect()

    before = datetime.now(UTC)

    observation = await provider.get_observation(
        "XAUUSD"
    )

    after = datetime.now(UTC)

    assert observation.symbol == "XAUUSD"
    assert observation.price == Decimal("4378.15000")
    assert observation.source == "Twelve Data"

    assert (
        observation.price_type
        is PriceObservationType.MID
    )

    assert before <= observation.timestamp <= after

    transport.get_json.assert_awaited_once_with(
        "/price",
        params={
            "symbol": "XAU/USD",
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "symbol",
    [
        "XAUUSD",
        "xauusd",
        "XAU/USD",
        "XAU-USD",
        "C:XAUUSD",
    ],
)
async def test_get_observation_accepts_pair_formats(
    symbol: str,
) -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    transport.get_json.return_value = {
        "price": "4378.15",
    }

    provider = make_provider(
        transport
    )
    await provider.connect()

    observation = await provider.get_observation(
        symbol
    )

    assert observation.symbol == "XAUUSD"


@pytest.mark.asyncio
async def test_get_observation_rejects_invalid_symbol() -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    provider = make_provider(
        transport
    )
    await provider.connect()

    with pytest.raises(
        ValueError,
        match="three-letter codes",
    ):
        await provider.get_observation(
            "US30"
        )


@pytest.mark.asyncio
async def test_get_observation_raises_provider_error() -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    transport.get_json.return_value = {
        "status": "error",
        "code": 400,
        "message": "Invalid symbol",
    }

    provider = make_provider(
        transport
    )
    await provider.connect()

    with pytest.raises(
        RuntimeError,
        match="Invalid symbol",
    ):
        await provider.get_observation(
            "XAUUSD"
        )


@pytest.mark.asyncio
async def test_get_observation_rejects_missing_price() -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    transport.get_json.return_value = {}

    provider = make_provider(
        transport
    )
    await provider.connect()

    with pytest.raises(
        RuntimeError,
        match="price",
    ):
        await provider.get_observation(
            "XAUUSD"
        )


@pytest.mark.asyncio
async def test_get_candles_normalizes_results() -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    transport.get_json.return_value = {
        "meta": {
            "symbol": "XAU/USD",
            "interval": "5min",
        },
        "values": [
            {
                "datetime": "2026-09-07 10:00:00",
                "open": "4377.50",
                "high": "4378.50",
                "low": "4377.20",
                "close": "4378.10",
            },
            {
                "datetime": "2026-09-07 10:05:00",
                "open": "4378.10",
                "high": "4379.00",
                "low": "4377.90",
                "close": "4378.70",
            },
        ],
        "status": "ok",
    }

    provider = make_provider(
        transport
    )
    await provider.connect()

    start = datetime(
        2026,
        9,
        7,
        9,
        55,
        tzinfo=UTC,
    )

    end = datetime(
        2026,
        9,
        7,
        10,
        10,
        tzinfo=UTC,
    )

    candles = await provider.get_candles(
        "XAUUSD",
        Timeframe.M5,
        start,
        end,
    )

    assert len(candles) == 2
    assert candles[0].symbol == "XAUUSD"
    assert candles[0].timeframe is Timeframe.M5

    assert (
        candles[0].open
        == Decimal("4377.50")
    )

    assert candles[0].volume == Decimal(0)

    assert candles[0].timestamp == datetime(
        2026,
        9,
        7,
        10,
        0,
        tzinfo=UTC,
    )

    transport.get_json.assert_awaited_once_with(
        "/time_series",
        params={
            "symbol": "XAU/USD",
            "interval": "5min",
            "timezone": "UTC",
            "start_date": "2026-09-07T09:55:00",
            "end_date": "2026-09-07T10:10:00",
            "order": "asc",
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("timeframe", "interval"),
    [
        (Timeframe.M1, "1min"),
        (Timeframe.M5, "5min"),
        (Timeframe.M15, "15min"),
        (Timeframe.M30, "30min"),
        (Timeframe.H1, "1h"),
        (Timeframe.H4, "4h"),
        (Timeframe.D1, "1day"),
    ],
)
async def test_get_candles_maps_intervals(
    timeframe: Timeframe,
    interval: str,
) -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    transport.get_json.return_value = {
        "meta": {},
        "values": [],
        "status": "ok",
    }

    provider = make_provider(
        transport
    )
    await provider.connect()

    start = datetime(
        2026,
        9,
        7,
        8,
        0,
        tzinfo=UTC,
    )

    end = datetime(
        2026,
        9,
        7,
        12,
        0,
        tzinfo=UTC,
    )

    await provider.get_candles(
        "EURUSD",
        timeframe,
        start,
        end,
    )

    transport.get_json.assert_awaited_once_with(
        "/time_series",
        params={
            "symbol": "EUR/USD",
            "interval": interval,
            "timezone": "UTC",
            "start_date": "2026-09-07T08:00:00",
            "end_date": "2026-09-07T12:00:00",
            "order": "asc",
        },
    )


@pytest.mark.asyncio
async def test_get_candles_sorts_results() -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    transport.get_json.return_value = {
        "values": [
            {
                "datetime": "2026-09-07 10:05:00",
                "open": "1.10",
                "high": "1.20",
                "low": "1.00",
                "close": "1.15",
            },
            {
                "datetime": "2026-09-07 10:00:00",
                "open": "1.05",
                "high": "1.15",
                "low": "1.00",
                "close": "1.10",
            },
        ],
        "status": "ok",
    }

    provider = make_provider(
        transport
    )
    await provider.connect()

    candles = await provider.get_candles(
        "EURUSD",
        Timeframe.M5,
        datetime(
            2026,
            9,
            7,
            9,
            55,
            tzinfo=UTC,
        ),
        datetime(
            2026,
            9,
            7,
            10,
            10,
            tzinfo=UTC,
        ),
    )

    assert (
        candles[0].timestamp
        < candles[1].timestamp
    )


@pytest.mark.asyncio
async def test_get_candles_rejects_invalid_range() -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    provider = make_provider(
        transport
    )
    await provider.connect()

    timestamp = datetime(
        2026,
        9,
        7,
        10,
        0,
        tzinfo=UTC,
    )

    with pytest.raises(
        ValueError,
        match="start must be earlier",
    ):
        await provider.get_candles(
            "EURUSD",
            Timeframe.M5,
            timestamp,
            timestamp,
        )


@pytest.mark.asyncio
async def test_get_candles_rejects_invalid_values_shape() -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    transport.get_json.return_value = {
        "values": {
            "unexpected": "object",
        },
        "status": "ok",
    }

    provider = make_provider(
        transport
    )
    await provider.connect()

    with pytest.raises(
        TypeError,
        match="'values' must be a list",
    ):
        await provider.get_candles(
            "EURUSD",
            Timeframe.M5,
            datetime(
                2026,
                9,
                7,
                8,
                0,
                tzinfo=UTC,
            ),
            datetime(
                2026,
                9,
                7,
                9,
                0,
                tzinfo=UTC,
            ),
        )


@pytest.mark.asyncio
async def test_get_candles_raises_provider_error() -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    transport.get_json.return_value = {
        "status": "error",
        "message": "API credits exhausted",
    }

    provider = make_provider(
        transport
    )
    await provider.connect()

    with pytest.raises(
        RuntimeError,
        match="API credits exhausted",
    ):
        await provider.get_candles(
            "EURUSD",
            Timeframe.M5,
            datetime(
                2026,
                9,
                7,
                8,
                0,
                tzinfo=UTC,
            ),
            datetime(
                2026,
                9,
                7,
                9,
                0,
                tzinfo=UTC,
            ),
        )