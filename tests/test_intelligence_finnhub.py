from datetime import UTC, datetime

import pytest

from packages.intelligence.finnhub import FinnhubMarketIntelligenceProvider


def test_provider_requires_api_key() -> None:
    with pytest.raises(ValueError, match="api_key"):
        FinnhubMarketIntelligenceProvider(api_key="")


def test_provider_requires_category() -> None:
    with pytest.raises(ValueError, match="category"):
        FinnhubMarketIntelligenceProvider(
            api_key="test-key",
            category=" ",
        )


def test_provider_name_is_finnhub() -> None:
    provider = FinnhubMarketIntelligenceProvider(
        api_key="test-key",
    )

    assert provider.name == "finnhub"


def test_parse_news_item() -> None:
    provider = FinnhubMarketIntelligenceProvider(
        api_key="test-key",
    )

    published_at = datetime(
        2026,
        9,
        5,
        12,
        0,
        tzinfo=UTC,
    )

    payload = [
        {
            "category": "business",
            "datetime": published_at.timestamp(),
            "headline": "Gold prices rise as markets assess rate expectations",
            "id": 12345,
            "related": "XAUUSD,USD",
            "source": "Reuters",
            "summary": "Markets reassess monetary-policy expectations.",
            "url": "https://example.com/article",
        }
    ]

    result = provider.parse_news(payload)

    assert len(result) == 1

    article = result[0]

    assert article.id == "finnhub-12345"
    assert article.external_id == "12345"
    assert article.provider == "finnhub"
    assert article.source == "Reuters"
    assert article.headline == (
        "Gold prices rise as markets assess rate expectations"
    )
    assert article.published_at == published_at
    assert article.symbols == ["XAUUSD", "USD"]
    assert article.event_type == "business"


def test_parse_news_normalizes_duplicate_symbols() -> None:
    provider = FinnhubMarketIntelligenceProvider(
        api_key="test-key",
    )

    payload = [
        {
            "category": "business",
            "datetime": 1788619321,
            "headline": "Test headline",
            "id": 123,
            "related": "xauusd, XAUUSD, usd",
            "source": "Reuters",
        }
    ]

    result = provider.parse_news(payload)

    assert result[0].symbols == ["XAUUSD", "USD"]


def test_parse_news_skips_malformed_records() -> None:
    provider = FinnhubMarketIntelligenceProvider(
        api_key="test-key",
    )

    payload = [
        {
            "category": "business",
            "datetime": 1788619321,
            "headline": "",
            "id": 123,
        },
        {
            "category": "business",
            "datetime": 1788619321,
            "headline": "Valid headline",
            "id": 456,
            "source": "Reuters",
        },
    ]

    result = provider.parse_news(payload)

    assert len(result) == 1
    assert result[0].external_id == "456"


def test_parse_news_accepts_string_article_id() -> None:
    provider = FinnhubMarketIntelligenceProvider(
        api_key="test-key",
    )

    payload = [
        {
            "category": "general",
            "datetime": 1788619321,
            "headline": "Test headline",
            "id": "abc-123",
            "source": "Finnhub",
        }
    ]

    result = provider.parse_news(payload)

    assert result[0].id == "finnhub-abc-123"
    assert result[0].external_id == "abc-123"


def test_parse_events_returns_empty() -> None:
    provider = FinnhubMarketIntelligenceProvider(
        api_key="test-key",
    )

    assert provider.parse_events([]) == []


def test_timestamp_range_filter() -> None:
    start = datetime(
        2026,
        9,
        5,
        10,
        0,
        tzinfo=UTC,
    )
    end = datetime(
        2026,
        9,
        5,
        12,
        0,
        tzinfo=UTC,
    )

    timestamp = datetime(
        2026,
        9,
        5,
        11,
        0,
        tzinfo=UTC,
    ).timestamp()

    assert FinnhubMarketIntelligenceProvider._is_timestamp_in_range(
        timestamp,
        start=start,
        end=end,
    )


def test_timestamp_range_rejects_outside_window() -> None:
    start = datetime(
        2026,
        9,
        5,
        10,
        0,
        tzinfo=UTC,
    )
    end = datetime(
        2026,
        9,
        5,
        12,
        0,
        tzinfo=UTC,
    )

    timestamp = datetime(
        2026,
        9,
        5,
        13,
        0,
        tzinfo=UTC,
    ).timestamp()

    assert not FinnhubMarketIntelligenceProvider._is_timestamp_in_range(
        timestamp,
        start=start,
        end=end,
    )