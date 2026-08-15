from collections.abc import Sequence
from decimal import Decimal

from packages.core.models import Candle


class MarketIndicators:
    """Deterministic technical indicators derived from OHLC candles."""

    @staticmethod
    def momentum_score(candles: Sequence[Candle]) -> float:
        """Return a normalized momentum score in the range [-1, 1]."""

        if len(candles) < 2:
            return 0.0

        previous = candles[-2].close
        current = candles[-1].close

        if previous <= Decimal(0):
            return 0.0

        change = (current - previous) / previous

        score = float(change * Decimal(100))

        return max(-1.0, min(1.0, score))

    @staticmethod
    def trend_score(candles: Sequence[Candle]) -> float:
        """Return a normalized trend score in the range [-1, 1]."""

        if len(candles) < 2:
            return 0.0

        first = candles[0].close
        last = candles[-1].close

        if first <= Decimal(0):
            return 0.0

        change = (last - first) / first

        score = float(change * Decimal(10))

        return max(-1.0, min(1.0, score))

    @staticmethod
    def volatility_score(candles: Sequence[Candle]) -> float:
        """Return normalized average candle-range volatility."""

        if not candles:
            return 0.0

        average_range = sum(
            (candle.range for candle in candles),
            Decimal(0),
        ) / Decimal(len(candles))

        average_price = sum(
            (candle.close for candle in candles),
            Decimal(0),
        ) / Decimal(len(candles))

        if average_price <= Decimal(0):
            return 0.0

        volatility = average_range / average_price

        score = float(volatility * Decimal(100))

        return max(0.0, min(1.0, score))