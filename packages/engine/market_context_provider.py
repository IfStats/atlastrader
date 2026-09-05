from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol

from packages.engine.market_context import MarketContext, MarketContextEngine
from packages.intelligence.gateway import MarketIntelligenceGateway
from packages.intelligence.impact import MarketImpactEngine
from packages.intelligence.normalizer import IntelligenceNormalizer
from packages.market_data.service import MarketDataService


class MarketContextProvider(Protocol):
    """Interface for retrieving combined market context."""

    async def get_market_context(self, symbol: str) -> MarketContext:
        """Return the latest combined market context for a symbol."""
        ...


class DefaultMarketContextProvider:
    """Build combined market context from market data and intelligence."""

    def __init__(
        self,
        *,
        market_data_service: MarketDataService,
        intelligence_gateway: MarketIntelligenceGateway,
        intelligence_normalizer: IntelligenceNormalizer | None = None,
        impact_engine: MarketImpactEngine | None = None,
        context_engine: MarketContextEngine | None = None,
        news_lookback: timedelta = timedelta(hours=24),
        event_horizon: timedelta = timedelta(days=7),
    ) -> None:
        if news_lookback <= timedelta(0):
            raise ValueError("news_lookback must be greater than zero")

        if event_horizon <= timedelta(0):
            raise ValueError("event_horizon must be greater than zero")

        self.market_data_service = market_data_service
        self.intelligence_gateway = intelligence_gateway
        self.intelligence_normalizer = (
            intelligence_normalizer or IntelligenceNormalizer()
        )
        self.impact_engine = impact_engine or MarketImpactEngine()
        self.context_engine = context_engine or MarketContextEngine()
        self.news_lookback = news_lookback
        self.event_horizon = event_horizon

    async def get_market_context(self, symbol: str) -> MarketContext:
        """Build the latest combined context for a symbol."""

        normalized_symbol = symbol.strip().upper()

        if not normalized_symbol:
            raise ValueError("symbol must not be empty")

        now = datetime.now(UTC)

        market_state = await self.market_data_service.get_market_state(
            normalized_symbol
        )

        news = await self.intelligence_gateway.get_news(
            start=now - self.news_lookback,
            end=now,
            symbols=[normalized_symbol],
        )

        events = await self.intelligence_gateway.get_events(
            start=now,
            end=now + self.event_horizon,
            symbols=[normalized_symbol],
        )

        normalized_intelligence = [
            self.intelligence_normalizer.normalize(item)
            for item in news
        ]

        intelligence = self.impact_engine.assess(
            intelligence=normalized_intelligence,
            events=events,
            now=now,
        )

        return self.context_engine.build(
            symbol=normalized_symbol,
            market_state=market_state,
            intelligence=intelligence,
        )