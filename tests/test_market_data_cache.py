from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from packages.core.enums import Timeframe
from packages.core.models import Candle, Quote
from packages.market_data.cache import MarketDataCache


def make_quote(symbol: str = "XAUUSD") -> Quote:
    return Quote(
        symbol=symbol,
        bid=Decimal("3350.25"),
        ask=Decimal("3350.45"),
        timestamp=datetime.now(UTC),
    )


def make_candles(symbol: str = "XAUUSD") -> list[Candle]:
    timestamp = datetime.now(UTC)

    return [
        Candle(
            symbol=symbol,
            timeframe=Timeframe.M5,
            timestamp=timestamp,
            open=Decimal(3340),
            high=Decimal(3346),
            low=Decimal(3338),
            close=Decimal(3345),
            volume=Decimal(1000),
        ),
        Candle(
            symbol=symbol,
            timeframe=Timeframe.M5,
            timestamp=timestamp + timedelta(minutes=5),
            open=Decimal(3345),
            high=Decimal(3351),
            low=Decimal(3343),
            close=Decimal(3350),
            volume=Decimal(1100),
        ),
    ]


def test_quote_cache_hit() -> None:
    cache = MarketDataCache()

    quote = make_quote()

    cache.set_quote(quote)

    assert cache.get_quote("XAUUSD") == quote


def test_quote_cache_miss_for_unknown_symbol() -> None:
    cache = MarketDataCache()

    assert cache.get_quote("XAUUSD") is None


def test_quote_cache_expires() -> None:
    cache = MarketDataCache(
        quote_ttl=timedelta(microseconds=1),
    )

    quote = make_quote()

    cache.set_quote(quote)

    import time

    time.sleep(0.001)

    assert cache.get_quote("XAUUSD") is None


def test_candle_cache_hit() -> None:
    cache = MarketDataCache()

    candles = make_candles()

    start = candles[0].timestamp
    end = candles[-1].timestamp

    cache.set_candles(
        "XAUUSD",
        Timeframe.M5,
        start,
        end,
        candles,
    )

    assert cache.get_candles(
        "XAUUSD",
        Timeframe.M5,
        start,
        end,
    ) == candles


def test_candle_cache_miss_for_different_window() -> None:
    cache = MarketDataCache()

    candles = make_candles()

    start = candles[0].timestamp
    end = candles[-1].timestamp

    cache.set_candles(
        "XAUUSD",
        Timeframe.M5,
        start,
        end,
        candles,
    )

    assert cache.get_candles(
        "XAUUSD",
        Timeframe.M5,
        start - timedelta(minutes=5),
        end,
    ) is None


def test_candle_cache_expires() -> None:
    cache = MarketDataCache(
        candle_ttl=timedelta(microseconds=1),
    )

    candles = make_candles()

    start = candles[0].timestamp
    end = candles[-1].timestamp

    cache.set_candles(
        "XAUUSD",
        Timeframe.M5,
        start,
        end,
        candles,
    )

    import time

    time.sleep(0.001)

    assert cache.get_candles(
        "XAUUSD",
        Timeframe.M5,
        start,
        end,
    ) is None


def test_clear_removes_all_cached_data() -> None:
    cache = MarketDataCache()

    quote = make_quote()
    candles = make_candles()

    start = candles[0].timestamp
    end = candles[-1].timestamp

    cache.set_quote(quote)
    cache.set_candles(
        "XAUUSD",
        Timeframe.M5,
        start,
        end,
        candles,
    )

    cache.clear()

    assert cache.get_quote("XAUUSD") is None
    assert cache.get_candles(
        "XAUUSD",
        Timeframe.M5,
        start,
        end,
    ) is None


def test_clear_symbol_removes_only_requested_symbol() -> None:
    cache = MarketDataCache()

    xau_quote = make_quote("XAUUSD")
    eur_quote = make_quote("EURUSD")

    xau_candles = make_candles("XAUUSD")
    eur_candles = make_candles("EURUSD")

    xau_start = xau_candles[0].timestamp
    xau_end = xau_candles[-1].timestamp

    eur_start = eur_candles[0].timestamp
    eur_end = eur_candles[-1].timestamp

    cache.set_quote(xau_quote)
    cache.set_quote(eur_quote)

    cache.set_candles(
        "XAUUSD",
        Timeframe.M5,
        xau_start,
        xau_end,
        xau_candles,
    )

    cache.set_candles(
        "EURUSD",
        Timeframe.M5,
        eur_start,
        eur_end,
        eur_candles,
    )

    cache.clear_symbol("XAUUSD")

    assert cache.get_quote("XAUUSD") is None
    assert cache.get_quote("EURUSD") == eur_quote

    assert cache.get_candles(
        "XAUUSD",
        Timeframe.M5,
        xau_start,
        xau_end,
    ) is None

    assert cache.get_candles(
        "EURUSD",
        Timeframe.M5,
        eur_start,
        eur_end,
    ) == eur_candles


@pytest.mark.parametrize(
    ("quote_ttl", "candle_ttl"),
    [
        (timedelta(0), timedelta(seconds=30)),
        (timedelta(seconds=-1), timedelta(seconds=30)),
        (timedelta(seconds=2), timedelta(0)),
        (timedelta(seconds=2), timedelta(seconds=-1)),
    ],
)
def test_cache_rejects_invalid_ttl(
    quote_ttl: timedelta,
    candle_ttl: timedelta,
) -> None:
    with pytest.raises(ValueError):
        MarketDataCache(
            quote_ttl=quote_ttl,
            candle_ttl=candle_ttl,
        )
