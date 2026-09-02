from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from decimal import Decimal

from packages.core.enums import MarketStatus, Timeframe
from packages.core.models import Candle, MarketState, Quote
from packages.market_data.base import MarketDataProvider
from packages.market_data.cache import MarketDataCache
from packages.market_data.indicators import MarketIndicators


class MarketDataService:
    """Build normalized market states from market-data providers."""

    def __init__(
        self,
        provider: MarketDataProvider,
        *,
        timeframe: Timeframe = Timeframe.M5,
        candle_lookback: int = 20,
        cache: MarketDataCache | None = None,
    ) -> None:
        if candle_lookback < 2:
            raise ValueError("candle_lookback must be at least 2")

        self.provider = provider
        self.timeframe = timeframe
        self.candle_lookback = candle_lookback
        self.cache = cache or MarketDataCache()

    async def get_market_state(self, symbol: str) -> MarketState:
        """Fetch market data and build an indicator-enriched MarketState."""
        quote = self.cache.get_quote(symbol)

        if quote is None:
            quote = await self.provider.get_quote(symbol)
            self.cache.set_quote(quote)

        end = quote.timestamp
        start = self._calculate_start_time(end)

        candles = self.cache.get_candles(
            symbol,
            self.timeframe,
            start,
            end,
        )

        if candles is None:
            candles = await self.provider.get_candles(
                symbol,
                self.timeframe,
                start,
                end,
            )
            self._validate_candles(
                candles,
                symbol,
                self.timeframe,
            )
            self.cache.set_candles(
                symbol,
                self.timeframe,
                start,
                end,
                candles,
            )
        else:
            self._validate_candles(
                candles,
                symbol,
                self.timeframe,
            )

        trend_score = MarketIndicators.trend_score(candles)
        momentum_score = MarketIndicators.momentum_score(candles)
        volatility_score = MarketIndicators.volatility_score(candles)
        volatility = self._calculate_volatility(candles)

        return MarketState(
            symbol=symbol,
            timestamp=quote.timestamp,
            timeframe=self.timeframe,
            price=quote.mid_price,
            trend_score=trend_score,
            momentum_score=momentum_score,
            volatility_score=volatility_score,
            volatility=volatility,
            spread=quote.spread,
            market_status=MarketStatus.OPEN,
            is_tradeable=self._is_tradeable(
                quote.spread,
                volatility,
            ),
        )

    async def stream_quotes(
        self,
        symbols: list[str],
        *,
        interval_seconds: float = 0.25,
    ) -> AsyncIterator[Quote]:
        """Stream live quotes while updating the normalized quote cache."""
        normalized_symbols = list(dict.fromkeys(symbols))

        if not normalized_symbols:
            raise ValueError("At least one symbol is required")

        if interval_seconds <= 0:
            raise ValueError(
                "interval_seconds must be greater than zero"
            )

        async for quote in self.provider.stream_quotes(
            normalized_symbols,
            interval_seconds=interval_seconds,
        ):
            self.cache.set_quote(quote)
            yield quote

    def _calculate_start_time(self, end: datetime) -> datetime:
        """Calculate the beginning of the candle lookback window."""
        timeframe_minutes = {
            Timeframe.M1: 1,
            Timeframe.M5: 5,
            Timeframe.M15: 15,
            Timeframe.M30: 30,
            Timeframe.H1: 60,
            Timeframe.H4: 240,
            Timeframe.D1: 1440,
        }

        minutes = timeframe_minutes[self.timeframe]

        return end - timedelta(
            minutes=minutes * self.candle_lookback,
        )

    def _validate_candles(
        self,
        candles: list[Candle],
        symbol: str,
        timeframe: Timeframe,
    ) -> None:
        """Validate the provider's historical candle series."""
        if len(candles) < self.candle_lookback:
            raise ValueError(
                "Insufficient candles: "
                f"expected at least {self.candle_lookback}, "
                f"received {len(candles)}"
            )

        previous_timestamp: datetime | None = None

        for candle in candles:
            if candle.symbol != symbol:
                raise ValueError(
                    "Candle symbol does not match requested symbol"
                )

            if candle.timeframe != timeframe:
                raise ValueError(
                    "Candle timeframe does not match requested timeframe"
                )

            if (
                previous_timestamp is not None
                and candle.timestamp <= previous_timestamp
            ):
                raise ValueError(
                    "Candle timestamps must be strictly increasing"
                )

            if candle.high < candle.low:
                raise ValueError(
                    "Candle high must be greater than or equal to low"
                )

            if candle.high < candle.open or candle.high < candle.close:
                raise ValueError(
                    "Candle high must be greater than or equal to "
                    "open and close"
                )

            if candle.low > candle.open or candle.low > candle.close:
                raise ValueError(
                    "Candle low must be less than or equal to "
                    "open and close"
                )

            previous_timestamp = candle.timestamp

    @staticmethod
    def _calculate_volatility(
        candles: list[Candle] | None = None,
    ) -> Decimal:
        """Calculate absolute average candle range."""
        if not candles:
            return Decimal(0)

        total_range = sum(
            (candle.range for candle in candles),
            Decimal(0),
        )

        return total_range / Decimal(len(candles))

    @staticmethod
    def _is_tradeable(
        spread: Decimal,
        volatility: Decimal,
    ) -> bool:
        """Determine whether the current market has usable price data."""
        if spread < Decimal(0):
            return False

        return not volatility < Decimal(0)