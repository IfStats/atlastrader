from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from packages.core.enums import Timeframe
from packages.market_data.http import (
    MarketDataHTTPTransport,
)
from packages.market_data.massive import (
    MassiveMarketDataProvider,
)


def make_provider(
    transport: AsyncMock,
) -> MassiveMarketDataProvider:
    return MassiveMarketDataProvider(
        api_key="test-api-key",
        transport=transport,
    )


def quote_payload(
    *,
    bid: float = 4377.98,
    ask: float = 4378.12,
    timestamp: int = 1788775200000,
) -> dict[str, object]:
    return {
        "last": {
            "bid": bid,
            "ask": ask,
            "timestamp": timestamp,
        },
        "status": "success",
        "symbol": "XAU/USD",
    }


@pytest.mark.asyncio
async def test_provider_rejects_empty_api_key() -> None:
    with pytest.raises(
        ValueError,
        match="api_key",
    ):
        MassiveMarketDataProvider(
            api_key="   "
        )


@pytest.mark.asyncio
async def test_provider_owned_transport_uses_bearer_auth() -> None:
    provider = MassiveMarketDataProvider(
        api_key="test-api-key",
    )

    assert (
        provider._transport.headers[
            "Authorization"
        ]
        == "Bearer test-api-key"
    )

    await provider.connect()

    assert provider._connected is True

    await provider.disconnect()

    assert provider._connected is False


@pytest.mark.asyncio
async def test_get_quote_requires_connection() -> None:
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
        await provider.get_quote(
            "XAUUSD"
        )


@pytest.mark.asyncio
async def test_get_quote_normalizes_massive_response() -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    transport.get_json.return_value = (
        quote_payload()
    )

    provider = make_provider(
        transport
    )
    await provider.connect()

    quote = await provider.get_quote(
        "XAUUSD"
    )

    assert quote.symbol == "XAUUSD"
    assert quote.bid == Decimal("4377.98")
    assert quote.ask == Decimal("4378.12")

    assert quote.timestamp == datetime(
        2026,
        9,
        7,
        10,
        0,
        tzinfo=UTC,
    )

    transport.get_json.assert_awaited_once_with(
        "/v1/last_quote/currencies/XAU/USD"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("symbol", "expected_symbol"),
    [
        ("xauusd", "XAUUSD"),
        ("XAU/USD", "XAUUSD"),
        ("C:XAUUSD", "XAUUSD"),
        ("XAU-USD", "XAUUSD"),
    ],
)
async def test_get_quote_accepts_supported_pair_formats(
    symbol: str,
    expected_symbol: str,
) -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    transport.get_json.return_value = (
        quote_payload()
    )

    provider = make_provider(
        transport
    )
    await provider.connect()

    quote = await provider.get_quote(
        symbol
    )

    assert (
        quote.symbol
        == expected_symbol
    )


@pytest.mark.asyncio
async def test_get_quote_rejects_invalid_pair_symbol() -> None:
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
        await provider.get_quote(
            "US30"
        )


@pytest.mark.asyncio
async def test_get_quote_rejects_missing_last_object() -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    transport.get_json.return_value = {
        "status": "success",
    }

    provider = make_provider(
        transport
    )
    await provider.connect()

    with pytest.raises(
        TypeError,
        match="'last'",
    ):
        await provider.get_quote(
            "XAUUSD"
        )


@pytest.mark.asyncio
async def test_get_quote_rejects_crossed_quote() -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    transport.get_json.return_value = (
        quote_payload(
            bid=4378.20,
            ask=4378.10,
        )
    )

    provider = make_provider(
        transport
    )
    await provider.connect()

    with pytest.raises(
        RuntimeError,
        match="ask below bid",
    ):
        await provider.get_quote(
            "XAUUSD"
        )


@pytest.mark.asyncio
async def test_get_candles_normalizes_and_sorts_results() -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    first_timestamp = 1788775200000
    second_timestamp = 1788775500000

    transport.get_json.return_value = {
        "status": "OK",
        "results": [
            {
                "o": 4378.10,
                "h": 4379.00,
                "l": 4377.90,
                "c": 4378.70,
                "v": 110,
                "t": second_timestamp,
            },
            {
                "o": 4377.50,
                "h": 4378.50,
                "l": 4377.20,
                "c": 4378.10,
                "v": 100,
                "t": first_timestamp,
            },
        ],
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
    ).replace(tzinfo=None)

    end = datetime(
        2026,
        9,
        7,
        10,
        10,
        tzinfo=UTC,
    ).replace(tzinfo=None)

    candles = await provider.get_candles(
        "XAUUSD",
        Timeframe.M5,
        start,
        end,
    )

    assert len(candles) == 2
    assert candles[0].symbol == "XAUUSD"

    assert (
        candles[0].timeframe
        is Timeframe.M5
    )

    assert (
        candles[0].open
        == Decimal("4377.5")
    )

    assert (
        candles[0].volume
        == Decimal(100)
    )

    assert (
        candles[0].timestamp
        < candles[1].timestamp
    )

    start_ms = int(
        start.timestamp() * 1000
    )
    end_ms = int(
        end.timestamp() * 1000
    )

    transport.get_json.assert_awaited_once_with(
        (
            f"/v2/aggs/ticker/C:XAUUSD/range/"
            f"5/minute/{start_ms}/{end_ms}"
        ),
        params={
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("timeframe", "multiplier", "timespan"),
    [
        (Timeframe.M1, 1, "minute"),
        (Timeframe.M5, 5, "minute"),
        (Timeframe.M15, 15, "minute"),
        (Timeframe.M30, 30, "minute"),
        (Timeframe.H1, 1, "hour"),
        (Timeframe.H4, 4, "hour"),
        (Timeframe.D1, 1, "day"),
    ],
)
async def test_get_candles_maps_timeframes(
    timeframe: Timeframe,
    multiplier: int,
    timespan: str,
) -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    transport.get_json.return_value = {
        "status": "OK",
        "results": [],
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

    start_ms = int(
        start.timestamp() * 1000
    )
    end_ms = int(
        end.timestamp() * 1000
    )

    transport.get_json.assert_awaited_once_with(
        (
            f"/v2/aggs/ticker/C:EURUSD/range/"
            f"{multiplier}/{timespan}/"
            f"{start_ms}/{end_ms}"
        ),
        params={
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
        },
    )


@pytest.mark.asyncio
async def test_get_candles_treats_naive_datetimes_as_utc() -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    transport.get_json.return_value = {
        "status": "OK",
        "results": [],
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
    ).replace(tzinfo=None)

    end = datetime(
        2026,
        9,
        7,
        9,
        0,
        tzinfo=UTC,
    ).replace(tzinfo=None)

    await provider.get_candles(
        "EURUSD",
        Timeframe.H1,
        start,
        end,
    )

    start_ms = int(
        start.replace(
            tzinfo=UTC
        ).timestamp()
        * 1000
    )

    end_ms = int(
        end.replace(
            tzinfo=UTC
        ).timestamp()
        * 1000
    )

    transport.get_json.assert_awaited_once_with(
        (
            f"/v2/aggs/ticker/C:EURUSD/range/"
            f"1/hour/{start_ms}/{end_ms}"
        ),
        params={
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
        },
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
async def test_get_candles_rejects_invalid_results_shape() -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    transport.get_json.return_value = {
        "status": "OK",
        "results": {
            "unexpected": "object"
        },
    }

    provider = make_provider(
        transport
    )
    await provider.connect()

    with pytest.raises(
        TypeError,
        match="'results' must be a list",
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
async def test_subscribe_and_unsubscribe_quotes() -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    provider = make_provider(
        transport
    )
    await provider.connect()

    await provider.subscribe_quotes(
        [
            "XAUUSD",
            "EUR/USD",
            "XAUUSD",
        ]
    )

    assert provider._subscribed_symbols == {
        "XAUUSD",
        "EURUSD",
    }

    await provider.unsubscribe_quotes(
        ["C:XAUUSD"]
    )

    assert provider._subscribed_symbols == {
        "EURUSD",
    }


@pytest.mark.asyncio
async def test_subscribe_quotes_rejects_empty_symbols() -> None:
    transport = AsyncMock(
        spec=MarketDataHTTPTransport
    )

    provider = make_provider(
        transport
    )
    await provider.connect()

    with pytest.raises(
        ValueError,
        match="At least one symbol",
    ):
        await provider.subscribe_quotes([])