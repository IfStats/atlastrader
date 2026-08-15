from datetime import UTC, datetime
from decimal import Decimal

from packages.core.enums import Timeframe
from packages.core.models import Candle, Quote
from packages.market_data.base import MarketDataProvider


class MockMarketDataProvider(MarketDataProvider):
    """Deterministic market-data provider for development and tests."""

    async def get_quote(self, symbol: str) -> Quote:
        return Quote(
            symbol=symbol,
            bid=Decimal("3348.21"),
            ask=Decimal("3348.42"),
            timestamp=datetime.now(UTC),
        )

    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        return [
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=start,
                open=Decimal("3345.00"),
                high=Decimal("3350.00"),
                low=Decimal("3343.00"),
                close=Decimal("3349.00"),
                volume=Decimal(1000),
            )
        ]

    async def subscribe_quotes(self, symbols: list[str]) -> None:
        return None

    async def unsubscribe_quotes(self, symbols: list[str]) -> None:
        return None