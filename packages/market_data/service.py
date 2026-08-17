from datetime import datetime, timedelta
from decimal import Decimal

from packages.core.enums import MarketStatus, Timeframe
from packages.core.models import Candle, MarketState
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
            self.cache.set_candles(
                symbol,
                self.timeframe,
                start,
                end,
                candles,
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