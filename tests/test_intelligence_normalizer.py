from datetime import UTC, datetime

import pytest

from packages.core.enums import SignalDirection
from packages.core.intelligence import MarketEvent, MarketNews
from packages.intelligence.normalizer import (
    ImpactAssessment,
    IntelligenceNormalizer,
    NormalizedIntelligence,
)

REFERENCE_TIME = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def make_news(
    headline: str,
    *,
    symbols: list[str] | None = None,
    provider: str = "Reuters",
    published_at: datetime = REFERENCE_TIME,
) -> MarketNews:
    return MarketNews(
        id="news-001",
        headline=headline,
        source=provider,
        provider=provider,
        published_at=published_at,
        symbols=symbols or [],
    )


def make_event(
    name: str,
    *,
    event_type: str = "economic",
    symbols: list[str] | None = None,
    scheduled_at: datetime = REFERENCE_TIME,
) -> MarketEvent:
    return MarketEvent(
        id="event-001",
        name=name,
        event_type=event_type,
        scheduled_at=scheduled_at,
        source="Economic Calendar",
        symbols=symbols or [],
        importance=0.8,
    )


def get_assessment(
    result: NormalizedIntelligence, symbol: str
) -> ImpactAssessment:
    """Helper to retrieve a target symbol assessment from normalized output."""
    for assessment in result.assessments:
        if assessment.symbol == symbol:
            return assessment
    raise KeyError(f"Symbol '{symbol}' not found in assessments.")


@pytest.fixture
def normalizer() -> IntelligenceNormalizer:
    return IntelligenceNormalizer()


def test_normalizes_news(normalizer: IntelligenceNormalizer) -> None:
    news = make_news(
        "Gold prices surge as investors seek safe haven assets",
        symbols=["XAUUSD"],
    )

    result = normalizer.normalize(news)

    assert result.source_id == news.id
    assert result.provider == news.provider
    assert result.headline == news.headline
    assert "XAUUSD" in result.symbols
    assert result.sentiment_score > 0
    assert result.relevance_score >= 0
    assert result.impact_score >= 0

def test_neutral_news_produces_flat_direction(
    normalizer: IntelligenceNormalizer,
) -> None:
    news = make_news(
        "Gold trades quietly ahead of the session",
        symbols=["XAUUSD"],
    )

    result = normalizer.normalize(news)
    assessment = get_assessment(result, "XAUUSD")

    assert assessment.direction is SignalDirection.FLAT


def test_positive_gold_news_produces_long_direction(
    normalizer: IntelligenceNormalizer,
) -> None:
    news = make_news(
        "Gold surges as investors seek safe haven assets",
        symbols=["XAUUSD"],
    )

    result = normalizer.normalize(news)
    assessment = get_assessment(result, "XAUUSD")

    assert result.sentiment_score > 0
    assert assessment.direction is SignalDirection.LONG


def test_negative_gold_news_produces_short_direction(
    normalizer: IntelligenceNormalizer,
) -> None:
    news = make_news(
        "Gold falls as investors abandon safe haven assets",
        symbols=["XAUUSD"],
    )

    result = normalizer.normalize(news)
    assessment = get_assessment(result, "XAUUSD")

    assert result.sentiment_score < 0
    assert assessment.direction is SignalDirection.SHORT


def test_hawkish_fed_headline_can_override_neutral_generic_sentiment(
    normalizer: IntelligenceNormalizer,
) -> None:
    news = make_news(
        "Fed signals higher for longer interest rates",
        symbols=["XAUUSD"],
    )

    result = normalizer.normalize(news)
    assessment = get_assessment(result, "XAUUSD")

    assert assessment.direction is SignalDirection.SHORT


def test_dovish_fed_headline_can_override_neutral_generic_sentiment(
    normalizer: IntelligenceNormalizer,
) -> None:
    news = make_news(
        "Fed signals rate cuts as inflation cools",
        symbols=["XAUUSD"],
    )

    result = normalizer.normalize(news)
    assessment = get_assessment(result, "XAUUSD")

    assert assessment.direction is SignalDirection.LONG


def test_rate_hike_is_bearish_for_gold(
    normalizer: IntelligenceNormalizer,
) -> None:
    news = make_news(
        "Federal Reserve raises interest rates",
        symbols=["XAUUSD"],
    )

    result = normalizer.normalize(news)
    assessment = get_assessment(result, "XAUUSD")

    assert assessment.direction is SignalDirection.SHORT\


def test_rate_cut_is_bullish_for_gold(
    normalizer: IntelligenceNormalizer,
) -> None:
    news = make_news(
        "Federal Reserve cuts interest rates",
        symbols=["XAUUSD"],
    )

    result = normalizer.normalize(news)
    assessment = get_assessment(result, "XAUUSD")

    assert assessment.direction is SignalDirection.LONG


def test_commodity_direction_is_asset_specific(
    normalizer: IntelligenceNormalizer,
) -> None:
    news = make_news(
        "Oil prices surge after major supply disruption",
        symbols=["USOIL"],
    )

    result = normalizer.normalize(news)
    assessment = get_assessment(result, "USOIL")

    assert assessment.direction is SignalDirection.LONG


def test_symbol_normalization_removes_duplicates(
    normalizer: IntelligenceNormalizer,
) -> None:
    news = make_news(
        "Gold market update",
        symbols=["xauusd", "XAUUSD", "XauUsd"],
    )

    result = normalizer.normalize(news)

    assert result.symbols == ["XAUUSD"]


def test_entity_extraction_detects_federal_reserve(
    normalizer: IntelligenceNormalizer,
) -> None:
    news = make_news(
        "Federal Reserve officials discuss monetary policy",
        symbols=["XAUUSD"],
    )

    result = normalizer.normalize(news)

    assert "Federal Reserve" in result.entities


def test_event_classification_detects_monetary_policy(
    normalizer: IntelligenceNormalizer,
) -> None:
    news = make_news(
        "Federal Reserve signals a change in interest rates",
        symbols=["XAUUSD"],
    )

    result = normalizer.normalize(news)

    assert result.event_type == "monetary_policy"


def test_event_classification_detects_geopolitical_news(
    normalizer: IntelligenceNormalizer,
) -> None:
    news = make_news(
        "Geopolitical tensions escalate in the region",
        symbols=["XAUUSD"],
    )

    result = normalizer.normalize(news)

    assert result.event_type == "geopolitical"


def test_event_classification_detects_commodity_news(
    normalizer: IntelligenceNormalizer,
) -> None:
    news = make_news(
        "Oil supply disruption pushes crude prices higher",
        symbols=["USOIL"],
    )

    result = normalizer.normalize(news)

    assert result.event_type == "commodity"


def test_scores_remain_within_declared_bounds(
    normalizer: IntelligenceNormalizer,
) -> None:
    news = make_news(
        "Markets react strongly to unexpected economic developments",
        symbols=["XAUUSD"],
    )

    result = normalizer.normalize(news)

    assert -1.0 <= result.sentiment_score <= 1.0
    assert 0.0 <= result.relevance_score <= 1.0
    assert 0.0 <= result.impact_score <= 1.0

    for assessment in result.assessments:
        assert 0.0 <= assessment.impact_score <= 1.0
        assert 0.0 <= assessment.confidence <= 1.0


def test_assessment_contains_rationale(
    normalizer: IntelligenceNormalizer,
) -> None:
    news = make_news(
        "Gold surges after safe haven demand increases",
        symbols=["XAUUSD"],
    )

    result = normalizer.normalize(news)
    assessment = get_assessment(result, "XAUUSD")

    assert len(assessment.rationale) > 0


def test_news_without_symbols_can_still_be_normalized(
    normalizer: IntelligenceNormalizer,
) -> None:
    news = make_news(
        "Federal Reserve officials comment on the economy",
    )

    result = normalizer.normalize(news)

    assert result.source_id == news.id
    assert result.headline == news.headline
    assert result.symbols == []
