from decimal import Decimal

from packages.core.enums import MarketStatus, Timeframe
from packages.core.models import MarketState
from packages.market_data.base import MarketDataProvider


class MarketDataService:
    """Build normalized market states from a market-data provider."""

    def __init__(
        self,
        provider: MarketDataProvider,
        *,
        timeframe: Timeframe = Timeframe.M5,
    ) -> None:
        self.provider = provider
        self.timeframe = timeframe

    async def get_market_state(self, symbol: str) -> MarketState:
        """Fetch the latest quote and convert it into a MarketState."""

        quote = await self.provider.get_quote(symbol)

        market_status = MarketStatus.OPEN
        is_tradeable = (
            market_status is MarketStatus.OPEN
            and quote.spread >= Decimal(0)
        )

        return MarketState(
            symbol=symbol,
            timestamp=quote.timestamp,
            timeframe=self.timeframe,
            price=quote.mid_price,
            trend_score=0.0,
            momentum_score=0.0,
            volatility_score=0.0,
            volatility=Decimal(0),
            spread=quote.spread,
            market_status=market_status,
            is_tradeable=is_tradeable,
        )