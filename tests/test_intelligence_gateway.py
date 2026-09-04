from datetime import UTC, datetime, timedelta

import pytest

from packages.core.intelligence import MarketEvent, MarketNews
from packages.intelligence.gateway import MarketIntelligenceGateway
from packages.intelligence.mock import MockMarketIntelligenceProvider


def make_news(
    news_id: str,
    *,
    symbol: str = "XAUUSD",
    published_at: datetime | None = None,
    provider: str | None = None,
    external_id: str | None = None,
) -> MarketNews:
    return MarketNews(
        id=news_id,
        headline=f"Headline {news_id}",
        source="Test Source",
        published_at=published_at
        or datetime(2026, 9, 4, 8, 0, tzinfo=UTC),
        symbols=[symbol],
        sentiment_score=0.5,
        relevance_score=0.9,
        impact_score=0.8,
        provider=provider,
        external_id=external_id,
    )


def make_event(
    event_id: str,
    *,
    symbol: str = "XAUUSD",
    scheduled_at: datetime | None = None,
    provider: str | None = None,
    external_id: str | None = None,
) -> MarketEvent:
    return MarketEvent(
        id=event_id,
        name=f"Event {event_id}",
        event_type="economic_release",
        scheduled_at=scheduled_at
        or datetime(2026, 9, 4, 9, 0, tzinfo=UTC),
        source="Test Calendar",
        symbols=[symbol],
        importance=0.9,
        is_confirmed=True,
        provider=provider,
        external_id=external_id,
    )


def make_gateway(
    *providers: MockMarketIntelligenceProvider,
    news_max_age: timedelta = timedelta(hours=1),
    event_max_age: timedelta = timedelta(hours=24),
) -> MarketIntelligenceGateway:
    return MarketIntelligenceGateway(
        providers=list(providers),
        news_max_age=news_max_age,
        event_max_age=event_max_age,
    )


@pytest.mark.asyncio
async def test_requires_at_least_one_provider() -> None:
    with pytest.raises(
        ValueError,
        match="At least one intelligence provider is required",
    ):
        MarketIntelligenceGateway(providers=[])


@pytest.mark.asyncio
async def test_rejects_non_positive_news_max_age() -> None:
    provider = MockMarketIntelligenceProvider()

    with pytest.raises(ValueError, match="news_max_age must be greater than zero"):
        make_gateway(provider, news_max_age=timedelta(0))


@pytest.mark.asyncio
async def test_rejects_non_positive_event_max_age() -> None:
    provider = MockMarketIntelligenceProvider()

    with pytest.raises(ValueError, match="event_max_age must be greater than zero"):
        make_gateway(provider, event_max_age=timedelta(0))


@pytest.mark.asyncio
async def test_get_news_merges_results_from_multiple_providers() -> None:
    timestamp = datetime(2026, 9, 4, 8, 0, tzinfo=UTC)

    provider_one = MockMarketIntelligenceProvider(
        provider_name="provider-one",
        news=[make_news("news-1", published_at=timestamp)],
    )
    provider_two = MockMarketIntelligenceProvider(
        provider_name="provider-two",
        news=[make_news("news-2", published_at=timestamp)],
    )

    gateway = make_gateway(provider_one, provider_two)

    result = await gateway.get_news(
        start=timestamp - timedelta(minutes=5),
        end=timestamp + timedelta(minutes=5),
    )

    assert {item.id for item in result} == {"news-1", "news-2"}


@pytest.mark.asyncio
async def test_get_events_merges_results_from_multiple_providers() -> None:
    timestamp = datetime(2026, 9, 4, 9, 0, tzinfo=UTC)

    provider_one = MockMarketIntelligenceProvider(
        provider_name="provider-one",
        events=[make_event("event-1", scheduled_at=timestamp)],
    )
    provider_two = MockMarketIntelligenceProvider(
        provider_name="provider-two",
        events=[make_event("event-2", scheduled_at=timestamp)],
    )

    gateway = make_gateway(provider_one, provider_two)

    result = await gateway.get_events(
        start=timestamp - timedelta(minutes=5),
        end=timestamp + timedelta(minutes=5),
    )

    assert {item.id for item in result} == {"event-1", "event-2"}


@pytest.mark.asyncio
async def test_news_is_deduplicated_by_provider_and_external_id() -> None:
    timestamp = datetime(2026, 9, 4, 8, 0, tzinfo=UTC)

    first = make_news(
        "news-a",
        published_at=timestamp,
        provider="provider-one",
        external_id="external-1",
    )
    duplicate = make_news(
        "news-b",
        published_at=timestamp,
        provider="provider-one",
        external_id="external-1",
    )

    provider = MockMarketIntelligenceProvider(
        provider_name="provider-one",
        news=[first, duplicate],
    )

    gateway = make_gateway(provider)

    result = await gateway.get_news(
        start=timestamp - timedelta(minutes=5),
        end=timestamp + timedelta(minutes=5),
    )

    assert len(result) == 1
    assert result[0].id == "news-a"


@pytest.mark.asyncio
async def test_events_are_deduplicated_by_provider_and_external_id() -> None:
    timestamp = datetime(2026, 9, 4, 9, 0, tzinfo=UTC)

    first = make_event(
        "event-a",
        scheduled_at=timestamp,
        provider="provider-one",
        external_id="external-1",
    )
    duplicate = make_event(
        "event-b",
        scheduled_at=timestamp,
        provider="provider-one",
        external_id="external-1",
    )

    provider = MockMarketIntelligenceProvider(
        provider_name="provider-one",
        events=[first, duplicate],
    )

    gateway = make_gateway(provider)

    result = await gateway.get_events(
        start=timestamp - timedelta(minutes=5),
        end=timestamp + timedelta(minutes=5),
    )

    assert len(result) == 1
    assert result[0].id == "event-a"


@pytest.mark.asyncio
async def test_news_provenance_is_added_when_missing() -> None:
    timestamp = datetime(2026, 9, 4, 8, 0, tzinfo=UTC)

    provider = MockMarketIntelligenceProvider(
        provider_name="ReutersProvider",
        news=[make_news("news-1", published_at=timestamp)],
    )

    gateway = make_gateway(provider)

    result = await gateway.get_news(
        start=timestamp - timedelta(minutes=5),
        end=timestamp + timedelta(minutes=5),
    )

    assert len(result) == 1
    assert result[0].provider == "ReutersProvider"
    assert result[0].external_id == "news-1"


@pytest.mark.asyncio
async def test_event_provenance_is_added_when_missing() -> None:
    timestamp = datetime(2026, 9, 4, 9, 0, tzinfo=UTC)

    provider = MockMarketIntelligenceProvider(
        provider_name="BloombergProvider",
        events=[make_event("event-1", scheduled_at=timestamp)],
    )

    gateway = make_gateway(provider)

    result = await gateway.get_events(
        start=timestamp - timedelta(minutes=5),
        end=timestamp + timedelta(minutes=5),
    )

    assert len(result) == 1
    assert result[0].provider == "BloombergProvider"
    assert result[0].external_id == "event-1"


@pytest.mark.asyncio
async def test_news_symbol_filter_is_applied() -> None:
    timestamp = datetime(2026, 9, 4, 8, 0, tzinfo=UTC)

    provider = MockMarketIntelligenceProvider(
        provider_name="provider-one",
        news=[
            make_news("gold-news", symbol="XAUUSD", published_at=timestamp),
            make_news("eur-news", symbol="EURUSD", published_at=timestamp),
        ],
    )

    gateway = make_gateway(provider)

    result = await gateway.get_news(
        start=timestamp - timedelta(minutes=5),
        end=timestamp + timedelta(minutes=5),
        symbols=["XAUUSD"],
    )

    assert [item.id for item in result] == ["gold-news"]


@pytest.mark.asyncio
async def test_collect_preserves_provider_runtime_errors() -> None:
    class FailingProvider(MockMarketIntelligenceProvider):
        @property
        def name(self) -> str:
            return "failing-provider"

        async def get_news(
            self,
            *,
            start: datetime,
            end: datetime,
            symbols: list[str] | None = None,
        ) -> list[MarketNews]:
            raise RuntimeError("news service unavailable")

        async def get_events(
            self,
            *,
            start: datetime,
            end: datetime,
            symbols: list[str] | None = None,
        ) -> list[MarketEvent]:
            raise RuntimeError("event service unavailable")

    timestamp = datetime(2026, 9, 4, 8, 0, tzinfo=UTC)

    healthy_provider = MockMarketIntelligenceProvider(
        provider_name="healthy-provider",
        news=[make_news("news-1", published_at=timestamp)],
        events=[make_event("event-1", scheduled_at=timestamp)],
    )

    gateway = make_gateway(healthy_provider, FailingProvider())

    snapshot = await gateway.collect(
        start=timestamp - timedelta(minutes=5),
        end=timestamp + timedelta(minutes=5),
        now=timestamp,
    )

    assert [item.id for item in snapshot.news] == ["news-1"]
    assert [item.id for item in snapshot.events] == ["event-1"]
    assert "failing-provider" in snapshot.provider_errors
    assert "news service unavailable" in snapshot.provider_errors["failing-provider"]
    assert "event service unavailable" in snapshot.provider_errors["failing-provider"]


@pytest.mark.asyncio
async def test_collect_applies_news_freshness() -> None:
    now = datetime(2026, 9, 4, 10, 0, tzinfo=UTC)

    fresh = make_news(
        "fresh",
        published_at=now - timedelta(minutes=30),
    )
    stale = make_news(
        "stale",
        published_at=now - timedelta(hours=2),
    )

    provider = MockMarketIntelligenceProvider(
        provider_name="provider-one",
        news=[fresh, stale],
    )

    gateway = make_gateway(
        provider,
        news_max_age=timedelta(hours=1),
    )

    snapshot = await gateway.collect(
        start=now - timedelta(days=1),
        end=now,
        now=now,
    )

    assert [item.id for item in snapshot.news] == ["fresh"]


@pytest.mark.asyncio
async def test_collect_applies_event_freshness() -> None:
    now = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)

    fresh = make_event(
        "fresh-event",
        scheduled_at=now - timedelta(hours=12),
    )
    stale = make_event(
        "stale-event",
        scheduled_at=now - timedelta(hours=48),
    )

    provider = MockMarketIntelligenceProvider(
        provider_name="provider-one",
        events=[fresh, stale],
    )

    gateway = make_gateway(
        provider,
        event_max_age=timedelta(hours=24),
    )

    snapshot = await gateway.collect(
        start=now - timedelta(days=3),
        end=now,
        now=now,
    )

    assert [item.id for item in snapshot.events] == ["fresh-event"]


@pytest.mark.asyncio
async def test_collect_returns_generated_timestamp() -> None:
    now = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)

    provider = MockMarketIntelligenceProvider()

    gateway = make_gateway(provider)

    snapshot = await gateway.collect(
        start=now - timedelta(hours=1),
        end=now,
        now=now,
    )

    assert snapshot.generated_at == now
