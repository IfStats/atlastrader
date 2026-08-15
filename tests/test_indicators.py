from datetime import UTC, datetime
from decimal import Decimal

from packages.core.enums import Timeframe
from packages.core.models import Candle
from packages.market_data.indicators import MarketIndicators


def make_candle(
    open_price: str,
    high: str,
    low: str,
    close: str,
) -> Candle:
    return Candle(
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        timestamp=datetime.now(UTC),
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
    )


def test_momentum_score_returns_zero_without_enough_data() -> None:
    candle = make_candle("100", "102", "99", "101")

    assert MarketIndicators.momentum_score([candle]) == 0.0


def test_momentum_score_detects_positive_move() -> None:
    candles = [
        make_candle("100", "101", "99", "100"),
        make_candle("100", "103", "99", "102"),
    ]

    score = MarketIndicators.momentum_score(candles)

    assert score > 0
    assert score <= 1


def test_momentum_score_detects_negative_move() -> None:
    candles = [
        make_candle("100", "101", "99", "100"),
        make_candle("100", "101", "97", "98"),
    ]

    score = MarketIndicators.momentum_score(candles)

    assert score < 0
    assert score >= -1


def test_trend_score_detects_uptrend() -> None:
    candles = [
        make_candle("100", "101", "99", "100"),
        make_candle("100", "103", "99", "102"),
        make_candle("102", "105", "101", "104"),
    ]

    score = MarketIndicators.trend_score(candles)

    assert score > 0
    assert score <= 1


def test_trend_score_detects_downtrend() -> None:
    candles = [
        make_candle("104", "105", "103", "104"),
        make_candle("104", "104", "100", "102"),
        make_candle("102", "103", "98", "100"),
    ]

    score = MarketIndicators.trend_score(candles)

    assert score < 0
    assert score >= -1


def test_volatility_score_returns_zero_without_candles() -> None:
    assert MarketIndicators.volatility_score([]) == 0.0


def test_volatility_score_is_positive() -> None:
    candles = [
        make_candle("100", "105", "95", "102"),
        make_candle("102", "108", "98", "106"),
    ]

    score = MarketIndicators.volatility_score(candles)

    assert score > 0
    assert score <= 1