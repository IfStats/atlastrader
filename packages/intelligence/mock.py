from datetime import datetime

from packages.core.intelligence import MarketEvent, MarketNews
from packages.intelligence.interfaces import MarketIntelligenceProvider


class MockMarketIntelligenceProvider(MarketIntelligenceProvider):
    def __init__(
        self,
        *,
        news: list[MarketNews] | None = None,
        events: list[MarketEvent] | None = None,
        provider_name: str | None = None,
    ) -> None:
        self._news = news or []
        self._events = events or []

        if provider_name is not None:
            self._provider_name = provider_name
        else:
            self._provider_name = self.__class__.__name__

    @property
    def name(self) -> str:
        return self._provider_name

    async def get_news(
        self,
        *,
        start: datetime,
        end: datetime,
        symbols: list[str] | None = None,
    ) -> list[MarketNews]:
        symbol_filter = (
            {symbol.upper() for symbol in symbols}
            if symbols is not None
            else None
        )

        return [
            item
            for item in self._news
            if start <= item.published_at <= end
            and (
                symbol_filter is None
                or symbol_filter.intersection(
                    {symbol.upper() for symbol in item.symbols}
                )
            )
        ]

    async def get_events(
        self,
        *,
        start: datetime,
        end: datetime,
        symbols: list[str] | None = None,
    ) -> list[MarketEvent]:
        symbol_filter = (
            {symbol.upper() for symbol in symbols}
            if symbols is not None
            else None
        )

        return [
            item
            for item in self._events
            if start <= item.scheduled_at <= end
            and (
                symbol_filter is None
                or symbol_filter.intersection(
                    {symbol.upper() for symbol in item.symbols}
                )
            )
        ]