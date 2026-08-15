from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from packages.core.enums import Timeframe
from packages.market_data.mt5 import MT5MarketDataProvider


def make_provider() -> MT5MarketDataProvider:
    return MT5MarketDataProvider()


@pytest.mark.asyncio
async def test_get_quote_requires_connection() -> None:
    provider = make_provider()

    with pytest.raises(RuntimeError, match="not connected"):
        await provider.get_quote("XAUUSD")


@pytest.mark.asyncio
async def test_get_quote_returns_normalized_quote() -> None:
    provider = make_provider()
    provider._connected = True

    tick = MagicMock()
    tick.bid = 3350.25
    tick.ask = 3350.45
    tick.time = int(datetime.now(UTC).timestamp())

    with patch(
        "packages.market_data.mt5.mt5.symbol_info_tick",
        return_value=tick,
    ):
        quote = await provider.get_quote("XAUUSD")

    assert quote.symbol == "XAUUSD"
    assert quote.bid == Decimal("3350.25")
    assert quote.ask == Decimal("3350.45")
    assert quote.spread == Decimal("0.20")


@pytest.mark.asyncio
async def test_get_quote_raises_when_tick_unavailable() -> None:
    provider = make_provider()
    provider._connected = True

    with (
        patch(
            "packages.market_data.mt5.mt5.symbol_info_tick",
            return_value=None,
        ),
        patch(
            "packages.market_data.mt5.mt5.last_error",
            return_value=(-10004, "No IPC connection"),
        ),pytest.raises(
        RuntimeError,
        match="Failed to retrieve quote for XAUUSD",
    )
    ):
        await provider.get_quote("XAUUSD")


@pytest.mark.asyncio
async def test_get_candles_returns_normalized_candles() -> None:
    provider = make_provider()
    provider._connected = True

    start = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    end = datetime(2026, 8, 15, 11, 0, tzinfo=UTC)

    rates = [
        {
            "time": int(
                datetime(
                    2026,
                    8,
                    15,
                    10,
                    0,
                    tzinfo=UTC,
                ).timestamp()
            ),
            "open": 3340.0,
            "high": 3355.0,
            "low": 3335.0,
            "close": 3350.0,
            "tick_volume": 1250,
        },
        {
            "time": int(
                datetime(
                    2026,
                    8,
                    15,
                    10,
                    5,
                    tzinfo=UTC,
                ).timestamp()
            ),
            "open": 3350.0,
            "high": 3360.0,
            "low": 3345.0,
            "close": 3358.0,
            "tick_volume": 1400,
        },
    ]

    with patch(
        "packages.market_data.mt5.mt5.copy_rates_range",
        return_value=rates,
    ):
        candles = await provider.get_candles(
            "XAUUSD",
            Timeframe.M5,
            start,
            end,
        )

    assert len(candles) == 2
    assert candles[0].symbol == "XAUUSD"
    assert candles[0].timeframe is Timeframe.M5
    assert candles[0].open == Decimal("3340.0")
    assert candles[0].high == Decimal("3355.0")
    assert candles[0].low == Decimal("3335.0")
    assert candles[0].close == Decimal("3350.0")
    assert candles[0].volume == Decimal(1250)

    assert candles[1].open == Decimal("3350.0")
    assert candles[1].high == Decimal("3360.0")
    assert candles[1].low == Decimal("3345.0")
    assert candles[1].close == Decimal("3358.0")
    assert candles[1].volume == Decimal(1400)


@pytest.mark.asyncio
async def test_get_candles_requires_connection() -> None:
    provider = make_provider()

    start = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    end = datetime(2026, 8, 15, 11, 0, tzinfo=UTC)

    with pytest.raises(RuntimeError, match="not connected"):
        await provider.get_candles(
            "XAUUSD",
            Timeframe.M5,
            start,
            end,
        )


@pytest.mark.asyncio
async def test_get_candles_rejects_invalid_date_range() -> None:
    provider = make_provider()
    provider._connected = True

    start = datetime(2026, 8, 15, 11, 0, tzinfo=UTC)
    end = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)

    with pytest.raises(
        ValueError,
        match="start must be earlier than end",
    ):
        await provider.get_candles(
            "XAUUSD",
            Timeframe.M5,
            start,
            end,
        )


@pytest.mark.asyncio
async def test_get_candles_raises_when_mt5_returns_none() -> None:
    provider = make_provider()
    provider._connected = True

    start = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    end = datetime(2026, 8, 15, 11, 0, tzinfo=UTC)

    with (
        patch(
            "packages.market_data.mt5.mt5.copy_rates_range",
            return_value=None,
        ),
        patch(
            "packages.market_data.mt5.mt5.last_error",
            return_value=(-10004, "No IPC connection"),
        ),pytest.raises(
        RuntimeError,
        match="Failed to retrieve candles for XAUUSD",
    )
    ):
        await provider.get_candles(
            "XAUUSD",
            Timeframe.M5,
            start,
            end,
        )



@pytest.mark.asyncio
async def test_get_candles_returns_empty_when_mt5_returns_empty() -> None:
    provider = make_provider()
    provider._connected = True

    start = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    end = datetime(2026, 8, 15, 11, 0, tzinfo=UTC)

    with patch(
        "packages.market_data.mt5.mt5.copy_rates_range",
        return_value=[],
    ):
        candles = await provider.get_candles(
            "XAUUSD",
            Timeframe.M5,
            start,
            end,
        )

    assert candles == []



@pytest.mark.asyncio
async def test_get_candles_maps_all_supported_timeframes() -> None:
    provider = make_provider()
    provider._connected = True

    start = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    end = datetime(2026, 8, 15, 11, 0, tzinfo=UTC)

    with patch(
        "packages.market_data.mt5.mt5.copy_rates_range",
        return_value=[],
    ) as mock_copy:
        for timeframe in Timeframe:
            await provider.get_candles(
                "XAUUSD",
                timeframe,
                start,
                end,
            )

            mock_copy.assert_called_with(
                "XAUUSD",
                provider._TIMEFRAME_MAP[timeframe],
                start,
                end,
            )


@pytest.mark.asyncio
async def test_get_candles_raises_when_mt5_returns_invalid_data() -> None:
    provider = make_provider()
    provider._connected = True

    start = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    end = datetime(2026, 8, 15, 11, 0, tzinfo=UTC)

    with (
        patch(
            "packages.market_data.mt5.mt5.copy_rates_range",
            return_value=None,
        ),
        patch(
            "packages.market_data.mt5.mt5.last_error",
            return_value=(-10004, "No IPC connection"),
        ),pytest.raises(
        RuntimeError,
        match="Failed to retrieve candles for INVALID",
    )
    ):
        await provider.get_candles(
            "INVALID",
            Timeframe.M5,
            start,
            end,
        )



@pytest.mark.asyncio
async def test_subscribe_quotes_requires_connection() -> None:
    provider = make_provider()

    with pytest.raises(RuntimeError, match="not connected"):
        await provider.subscribe_quotes(["XAUUSD"])


@pytest.mark.asyncio
async def test_unsubscribe_quotes_requires_connection() -> None:
    provider = make_provider()

    with pytest.raises(RuntimeError, match="not connected"):
        await provider.unsubscribe_quotes(["XAUUSD"])
