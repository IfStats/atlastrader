from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from packages.core.enums import MarketStatus, SignalDirection, Timeframe
from packages.core.models import MarketState
from packages.engine.market_context import MarketContextEngine
from packages.engine.market_context_provider import DefaultMarketContextProvider
from packages.intelligence.gateway import MarketIntelligenceGateway
from packages.intelligence.impact import MarketImpactEngine
from packages.intelligence.mock import MockMarketIntelligenceProvider
from packages.intelligence.normalizer import IntelligenceNormalizer
from packages.market_data.service import MarketDataService


def make_market_state() -> MarketState:
    return MarketState(
        symbol="XAUUSD",
        timestamp=datetime.now(UTC),
        timeframe=Timeframe.M5,
        price=Decimal("4377.97"),
        trend_score=0.80,
        momentum_score=0.70,
        volatility_score=0.20,
        volatility=Decimal("5.00"),
        spread=Decimal("0.10"),
        market_status=MarketStatus.OPEN,
        session="london",
        is_tradeable=True,
    )


def make_provider() -> tuple[
    DefaultMarketContextProvider,
    AsyncMock,
    MarketIntelligenceGateway,
]:
    market_data_service = AsyncMock(spec=MarketDataService)
    market_data_service.get_market_state.return_value = make_market_state()

    intelligence_gateway = MarketIntelligenceGateway(
        providers=[
            MockMarketIntelligenceProvider(
                provider_name="test-provider",
            )
        ]
    )

    provider = DefaultMarketContextProvider(
        market_data_service=market_data_service,
        intelligence_gateway=intelligence_gateway,
    )

    return provider, market_data_service, intelligence_gateway


@pytest.mark.asyncio
async def test_builds_market_context_from_market_data_and_intelligence() -> None:
    provider, market_data_service, _ = make_provider()

    context = await provider.get_market_context("xauusd")

    market_data_service.get_market_state.assert_awaited_once_with("XAUUSD")

    assert context.market_state.symbol == "XAUUSD"
    assert context.direction is SignalDirection.LONG
    assert context.combined_directional_score > 0
    assert context.combined_confidence > 0
    assert context.is_tradeable is True


@pytest.mark.asyncio
async def test_normalizes_symbol_before_market_data_lookup() -> None:
    provider, market_data_service, _ = make_provider()

    await provider.get_market_context("  xAuUsD  ")

    market_data_service.get_market_state.assert_awaited_once_with("XAUUSD")


@pytest.mark.asyncio
async def test_rejects_empty_symbol() -> None:
    provider, _, _ = make_provider()

    with pytest.raises(ValueError, match="symbol must not be empty"):
        await provider.get_market_context("   ")


@pytest.mark.asyncio
async def test_accepts_custom_component_configuration() -> None:
    provider, _, _ = make_provider()

    custom_context_engine = MarketContextEngine(
        technical_weight=0.70,
        intelligence_weight=0.30,
    )
    custom_impact_engine = MarketImpactEngine(
        intelligence_max_age=timedelta(hours=12),
        decay_floor=0.20,
    )

    configured_provider = DefaultMarketContextProvider(
        market_data_service=provider.market_data_service,
        intelligence_gateway=provider.intelligence_gateway,
        intelligence_normalizer=IntelligenceNormalizer(),
        impact_engine=custom_impact_engine,
        context_engine=custom_context_engine,
        news_lookback=timedelta(hours=12),
        event_horizon=timedelta(days=3),
    )

    context = await configured_provider.get_market_context("XAUUSD")

    assert context.market_state.symbol == "XAUUSD"
    assert configured_provider.news_lookback == timedelta(hours=12)
    assert configured_provider.event_horizon == timedelta(days=3)


@pytest.mark.asyncio
async def test_rejects_non_positive_time_windows() -> None:
    _, market_data_service, intelligence_gateway = make_provider()

    with pytest.raises(
        ValueError,
        match="news_lookback must be greater than zero",
    ):
        DefaultMarketContextProvider(
            market_data_service=market_data_service,
            intelligence_gateway=intelligence_gateway,
            news_lookback=timedelta(0),
        )

    with pytest.raises(
        ValueError,
        match="event_horizon must be greater than zero",
    ):
        DefaultMarketContextProvider(
            market_data_service=market_data_service,
            intelligence_gateway=intelligence_gateway,
            event_horizon=timedelta(0),
        )