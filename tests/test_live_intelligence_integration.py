from datetime import UTC, datetime, timedelta

import pytest

from packages.core.config import IntelligenceSettings
from packages.intelligence.finnhub import FinnhubMarketIntelligenceProvider
from packages.intelligence.gateway import MarketIntelligenceGateway
from packages.intelligence.impact import MarketImpactEngine
from packages.intelligence.normalizer import IntelligenceNormalizer


@pytest.mark.asyncio
async def test_live_finnhub_intelligence_pipeline() -> None:
    settings = IntelligenceSettings()

    if not settings.enabled:
        pytest.skip(
            "Set ATLAS_INTELLIGENCE_ENABLED=true temporarily "
            "for the live integration test."
        )

    if not settings.has_finnhub_credentials():
        pytest.skip("Finnhub API credentials are not configured.")

    provider = FinnhubMarketIntelligenceProvider(
        api_key=settings.finnhub_api_key or "",
        base_url=settings.finnhub_base_url,
        timeout_seconds=settings.request_timeout_seconds,
        max_retries=settings.max_retries,
        backoff_seconds=settings.retry_backoff_seconds,
    )

    gateway = MarketIntelligenceGateway(
        providers=[provider],
    )

    now = datetime.now(UTC)

    try:
        await provider.start()

        news = await gateway.get_news(
            start=now - timedelta(hours=24),
            end=now,
            symbols=["XAUUSD"],
        )

        assert isinstance(news, list)

        normalizer = IntelligenceNormalizer()
        normalized = [
            normalizer.normalize(article)
            for article in news
        ]

        impact_engine = MarketImpactEngine()
        impact = impact_engine.assess(
            intelligence=normalized,
            events=[],
            now=now,
        )

        assert impact is not None

    finally:
        await provider.close()