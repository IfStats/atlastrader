from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.core.intelligence import MarketEvent, MarketNews
from packages.intelligence.mock import MockMarketIntelligenceProvider


def make_news(
    *,
    news_id: str,
    symbol: str,
    minute: int,
) -> MarketNews:
    return MarketNews(
        id=news_id,
        headline=f"Market news {news_id}",
        source="TestSource",
        published_at=datetime(
            2026,
            9,
            4,
            10,
            minute,
            tzinfo=UTC,
        ),
        symbols=[symbol],
        sentiment_score=0.75,
        relevance_score=0.90,
        impact_score=0.80,
    )


def make_event(
    *,
    event_id: str,
    symbol: str,
    minute: int,
) -> MarketEvent:
    return MarketEvent(
        id=event_id,
        name="Test Economic Event",
        event_type="economic_release",
        scheduled_at=datetime(
            2026,
            9,
            4,
            10,
            minute,
            tzinfo=UTC,
        ),
        source="TestCalendar",
        symbols=[symbol],
        importance=0.95,
        expected_value=Decimal("3.0"),
        previous_value=Decimal("2.8"),
    )


@pytest.mark.asyncio
async def test_mock_provider_returns_news_in_time_range() -> None:
    news = [
        make_news(
            news_id="news-1",
            symbol="XAUUSD",
            minute=5,
        ),
        make_news(
            news_id="news-2",
            symbol="EURUSD",
            minute=30,
        ),
    ]

    provider = MockMarketIntelligenceProvider(news=news)

    results = await provider.get_news(
        start=datetime(2026, 9, 4, 10, 0, tzinfo=UTC),
        end=datetime(2026, 9, 4, 10, 10, tzinfo=UTC),
    )

    assert len(results) == 1
    assert results[0].id == "news-1"


@pytest.mark.asyncio
async def test_mock_provider_filters_news_by_symbol() -> None:
    news = [
        make_news(
            news_id="gold-news",
            symbol="XAUUSD",
            minute=5,
        ),
        make_news(
            news_id="eur-news",
            symbol="EURUSD",
            minute=5,
        ),
    ]

    provider = MockMarketIntelligenceProvider(news=news)

    results = await provider.get_news(
        start=datetime(2026, 9, 4, 10, 0, tzinfo=UTC),
        end=datetime(2026, 9, 4, 10, 10, tzinfo=UTC),
        symbols=["XAUUSD"],
    )

    assert len(results) == 1
    assert results[0].symbols == ["XAUUSD"]


@pytest.mark.asyncio
async def test_mock_provider_returns_events() -> None:
    event = make_event(
        event_id="event-1",
        symbol="XAUUSD",
        minute=20,
    )

    provider = MockMarketIntelligenceProvider(events=[event])

    results = await provider.get_events(
        start=datetime(2026, 9, 4, 10, 0, tzinfo=UTC),
        end=datetime(2026, 9, 4, 10, 30, tzinfo=UTC),
    )

    assert len(results) == 1
    assert results[0].id == "event-1"
    assert results[0].importance == 0.95


def test_market_news_validates_sentiment_range() -> None:
    with pytest.raises(ValueError):
        MarketNews(
            id="invalid-news",
            headline="Invalid",
            source="Test",
            published_at=datetime.now(UTC),
            sentiment_score=2.0,
        )


def test_market_event_validates_importance_range() -> None:
    with pytest.raises(ValueError):
        MarketEvent(
            id="invalid-event",
            name="Invalid",
            event_type="test",
            scheduled_at=datetime.now(UTC),
            source="Test",
            importance=2.0,
        )