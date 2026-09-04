
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

from packages.core.intelligence import MarketEvent, MarketNews
from packages.intelligence.interfaces import MarketIntelligenceProvider


class IntelligenceSnapshot(BaseModel):
    news: list[MarketNews] = Field(default_factory=list)
    events: list[MarketEvent] = Field(default_factory=list)
    provider_errors: dict[str, str] = Field(default_factory=dict)
    generated_at: datetime


class MarketIntelligenceGateway:
    """Aggregate and normalize intelligence from multiple providers."""

    def __init__(
        self,
        *,
        providers: list[MarketIntelligenceProvider],
        news_max_age: timedelta = timedelta(hours=24),
        event_max_age: timedelta = timedelta(days=7),
    ) -> None:
        if not providers:
            raise ValueError("At least one intelligence provider is required")

        if news_max_age <= timedelta(0):
            raise ValueError("news_max_age must be greater than zero")

        if event_max_age <= timedelta(0):
            raise ValueError("event_max_age must be greater than zero")

        self.providers = providers
        self.news_max_age = news_max_age
        self.event_max_age = event_max_age

    async def get_news(
        self,
        *,
        start: datetime,
        end: datetime,
        symbols: list[str] | None = None,
    ) -> list[MarketNews]:
        """Collect news from all providers."""
        snapshot = await self.collect(
            start=start,
            end=end,
            symbols=symbols,
            now=end,
        )
        return snapshot.news

    async def get_events(
        self,
        *,
        start: datetime,
        end: datetime,
        symbols: list[str] | None = None,
    ) -> list[MarketEvent]:
        """Collect events from all providers."""
        snapshot = await self.collect(
            start=start,
            end=end,
            symbols=symbols,
            now=end,
        )
        return snapshot.events

    async def collect(
        self,
        *,
        start: datetime,
        end: datetime,
        symbols: list[str] | None = None,
        now: datetime | None = None,
    ) -> IntelligenceSnapshot:
        """Collect news and events while preserving provider failures."""

        collected_news: list[MarketNews] = []
        collected_events: list[MarketEvent] = []
        provider_errors: dict[str, str] = {}

        for provider in self.providers:
            try:
                news = await provider.get_news(
                    start=start,
                    end=end,
                    symbols=symbols,
                )
                collected_news.extend(
                    self._apply_news_provenance(news, provider)
                )
            except RuntimeError as exc:
                provider_errors[provider.name] = (
                    f"news: {type(exc).__name__}: {exc}"
                )

            try:
                events = await provider.get_events(
                    start=start,
                    end=end,
                    symbols=symbols,
                )
                collected_events.extend(
                    self._apply_event_provenance(events, provider)
                )
            except RuntimeError as exc:
                existing = provider_errors.get(provider.name)
                error = f"events: {type(exc).__name__}: {exc}"

                if existing is not None:
                    provider_errors[provider.name] = f"{existing}; {error}"
                else:
                    provider_errors[provider.name] = error

        reference_time = now or datetime.now(UTC)

        news = self._filter_news(
            self._deduplicate_news(collected_news),
            symbols=symbols,
            now=reference_time,
        )

        events = self._filter_events(
            self._deduplicate_events(collected_events),
            symbols=symbols,
            now=reference_time,
        )

        return IntelligenceSnapshot(
            news=news,
            events=events,
            provider_errors=provider_errors,
            generated_at=reference_time,
        )

    @staticmethod
    def _apply_news_provenance(
        items: list[MarketNews],
        provider: MarketIntelligenceProvider,
    ) -> list[MarketNews]:
        return [
            item.model_copy(
                update={
                    "provider": item.provider or provider.name,
                    "external_id": item.external_id or item.id,
                }
            )
            for item in items
        ]

    @staticmethod
    def _apply_event_provenance(
        items: list[MarketEvent],
        provider: MarketIntelligenceProvider,
    ) -> list[MarketEvent]:
        return [
            item.model_copy(
                update={
                    "provider": item.provider or provider.name,
                    "external_id": item.external_id or item.id,
                }
            )
            for item in items
        ]

    @staticmethod
    def _deduplicate_news(
        items: list[MarketNews],
    ) -> list[MarketNews]:
        unique: dict[tuple[str, str], MarketNews] = {}

        for item in items:
            key = (
                item.provider or "",
                item.external_id or item.id,
            )
            existing = unique.get(key)

            if existing is None or item.published_at > existing.published_at:
                unique[key] = item

        return list(unique.values())

    @staticmethod
    def _deduplicate_events(
        items: list[MarketEvent],
    ) -> list[MarketEvent]:
        unique: dict[tuple[str, str], MarketEvent] = {}

        for item in items:
            key = (
                item.provider or "",
                item.external_id or item.id,
            )
            existing = unique.get(key)

            if existing is None or item.scheduled_at > existing.scheduled_at:
                unique[key] = item

        return list(unique.values())

    def _filter_news(
        self,
        items: list[MarketNews],
        *,
        symbols: list[str] | None,
        now: datetime,
    ) -> list[MarketNews]:
        symbol_filter = (
            {symbol.upper() for symbol in symbols}
            if symbols is not None
            else None
        )

        cutoff = now - self.news_max_age

        results = [
            item
            for item in items
            if cutoff <= item.published_at <= now
            and (
                symbol_filter is None
                or symbol_filter.intersection(
                    {symbol.upper() for symbol in item.symbols}
                )
            )
        ]

        return sorted(
            results,
            key=lambda item: item.published_at,
            reverse=True,
        )

    def _filter_events(
        self,
        items: list[MarketEvent],
        *,
        symbols: list[str] | None,
        now: datetime,
    ) -> list[MarketEvent]:
        symbol_filter = (
            {symbol.upper() for symbol in symbols}
            if symbols is not None
            else None
        )

        cutoff = now - self.event_max_age

        results = [
            item
            for item in items
            if cutoff <= item.scheduled_at <= now
            and (
                symbol_filter is None
                or symbol_filter.intersection(
                    {symbol.upper() for symbol in item.symbols}
                )
            )
        ]

        return sorted(
            results,
            key=lambda item: item.scheduled_at,
            reverse=True,
        )
