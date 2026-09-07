from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from packages.core.enums import (
    MarketStatus,
    Timeframe,
)
from packages.core.models import MarketState
from packages.engine.market_context import (
    MarketContextEngine,
)
from packages.engine.market_context_provider import (
    DefaultMarketContextProvider,
)
from packages.intelligence.gateway import (
    MarketIntelligenceGateway,
)
from packages.intelligence.impact import (
    MarketImpactContext,
)
from packages.market_data.comparison import (
    MarketDataComparisonStatus,
)
from packages.market_data.quality import (
    MarketDataQualityDecision,
)
from packages.market_data.service import (
    MarketDataService,
)

REFERENCE_TIME = datetime(
    2026,
    9,
    7,
    14,
    0,
    tzinfo=UTC,
)


def make_market_state() -> MarketState:
    return MarketState(
        symbol="XAUUSD",
        timestamp=REFERENCE_TIME,
        timeframe=Timeframe.M5,
        price=Decimal("4378.10"),
        trend_score=0.8,
        momentum_score=0.6,
        volatility_score=0.2,
        volatility=Decimal(5),
        spread=Decimal("0.10"),
        market_status=MarketStatus.OPEN,
        session="london",
        is_tradeable=True,
    )


def make_intelligence() -> MarketImpactContext:
    return MarketImpactContext(
        generated_at=REFERENCE_TIME,
        impacts=[],
        event_risk_score=0.0,
        high_impact_event_count=0,
    )


def make_quality_decision(
    *,
    status: MarketDataComparisonStatus,
    trading_permitted: bool,
    multiplier: float,
) -> MarketDataQualityDecision:
    return MarketDataQualityDecision(
        trading_permitted=trading_permitted,
        confidence_multiplier=multiplier,
        status=status,
        reasons=[],
    )


def test_no_quality_decision_preserves_existing_confidence() -> None:
    engine = MarketContextEngine()

    context = engine.build(
        symbol="XAUUSD",
        market_state=make_market_state(),
        intelligence=make_intelligence(),
    )

    assert context.combined_confidence == pytest.approx(
        0.42
    )

    assert context.is_tradeable is True
    assert context.market_data_quality is None


def test_degraded_quality_reduces_confidence() -> None:
    engine = MarketContextEngine()

    quality = make_quality_decision(
        status=MarketDataComparisonStatus.DEGRADED,
        trading_permitted=True,
        multiplier=0.5,
    )

    context = engine.build(
        symbol="XAUUSD",
        market_state=make_market_state(),
        intelligence=make_intelligence(),
        market_data_quality=quality,
    )

    assert context.combined_confidence == pytest.approx(
        0.21
    )

    assert context.is_tradeable is True
    assert context.market_data_quality == quality

    assert (
        "market_data_quality=degraded"
        in context.rationale
    )


def test_anomalous_quality_blocks_tradeability() -> None:
    engine = MarketContextEngine()

    quality = make_quality_decision(
        status=MarketDataComparisonStatus.ANOMALOUS,
        trading_permitted=False,
        multiplier=0.0,
    )

    context = engine.build(
        symbol="XAUUSD",
        market_state=make_market_state(),
        intelligence=make_intelligence(),
        market_data_quality=quality,
    )

    assert context.combined_confidence == 0.0
    assert context.is_tradeable is False

    assert (
        "market_data_quality=anomalous"
        in context.rationale
    )


@pytest.mark.asyncio
async def test_provider_applies_quality_provider_decision() -> None:
    market_data_service = AsyncMock(
        spec=MarketDataService
    )

    market_data_service.get_market_state.return_value = (
        make_market_state()
    )

    intelligence_gateway = AsyncMock(
        spec=MarketIntelligenceGateway
    )

    intelligence_gateway.get_news.return_value = []
    intelligence_gateway.get_events.return_value = []

    quality_provider = AsyncMock()

    quality_provider.get_quality_decision.return_value = (
        make_quality_decision(
            status=(
                MarketDataComparisonStatus.DEGRADED
            ),
            trading_permitted=True,
            multiplier=0.5,
        )
    )

    provider = DefaultMarketContextProvider(
        market_data_service=market_data_service,
        intelligence_gateway=intelligence_gateway,
        market_data_quality_provider=(
            quality_provider
        ),
    )

    context = await provider.get_market_context(
        " xauusd "
    )

    quality_provider.get_quality_decision.assert_awaited_once_with(
        "XAUUSD"
    )

    assert context.market_data_quality is not None

    assert (
        context.market_data_quality.status
        is MarketDataComparisonStatus.DEGRADED
    )

    assert context.combined_confidence == pytest.approx(
        0.21
    )

    assert context.is_tradeable is True