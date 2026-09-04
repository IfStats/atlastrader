from datetime import UTC, datetime, timedelta

from packages.core.enums import SignalDirection
from packages.core.intelligence import MarketEvent
from packages.intelligence.impact import MarketImpactEngine
from packages.intelligence.normalizer import (
    ImpactAssessment,
    NormalizedIntelligence,
)

REFERENCE_TIME = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def make_intelligence(
    *,
    symbol: str = "XAUUSD",
    direction: SignalDirection = SignalDirection.LONG,
    impact_score: float = 0.8,
    confidence: float = 0.9,
    published_at: datetime = REFERENCE_TIME,
) -> NormalizedIntelligence:
    return NormalizedIntelligence(
        source_id="news-001",
        provider="Reuters",
        headline="Gold market update",
        published_at=published_at,
        event_type="commodity",
        symbols=[symbol],
        sentiment_score=0.8,
        relevance_score=0.9,
        impact_score=impact_score,
        assessments=[
            ImpactAssessment(
                symbol=symbol,
                direction=direction,
                impact_score=impact_score,
                confidence=confidence,
                rationale=["test assessment"],
            )
        ],
    )


def make_event(
    *,
    importance: float = 0.8,
    scheduled_at: datetime = REFERENCE_TIME + timedelta(hours=1),
    confirmed: bool = True,
) -> MarketEvent:
    return MarketEvent(
        id="event-001",
        name="Federal Reserve Rate Decision",
        event_type="monetary_policy",
        scheduled_at=scheduled_at,
        source="Economic Calendar",
        symbols=["XAUUSD"],
        importance=importance,
        is_confirmed=confirmed,
    )


def test_positive_intelligence_produces_long_impact() -> None:
    engine = MarketImpactEngine()

    result = engine.assess(
        intelligence=[make_intelligence()],
        now=REFERENCE_TIME,
    )

    assert len(result.impacts) == 1

    impact = result.impacts[0]

    assert impact.symbol == "XAUUSD"
    assert impact.direction is SignalDirection.LONG
    assert impact.directional_score > 0
    assert impact.impact_score > 0
    assert impact.confidence > 0
    assert impact.news_count == 1


def test_negative_intelligence_produces_short_impact() -> None:
    engine = MarketImpactEngine()

    result = engine.assess(
        intelligence=[
            make_intelligence(direction=SignalDirection.SHORT)
        ],
        now=REFERENCE_TIME,
    )

    impact = result.impacts[0]

    assert impact.direction is SignalDirection.SHORT
    assert impact.directional_score < 0


def test_flat_intelligence_produces_flat_impact() -> None:
    engine = MarketImpactEngine()

    result = engine.assess(
        intelligence=[
            make_intelligence(direction=SignalDirection.FLAT)
        ],
        now=REFERENCE_TIME,
    )

    impact = result.impacts[0]

    assert impact.direction is SignalDirection.FLAT
    assert impact.directional_score == 0.0


def test_old_intelligence_is_excluded() -> None:
    engine = MarketImpactEngine(
        intelligence_max_age=timedelta(hours=24)
    )

    old_time = REFERENCE_TIME - timedelta(hours=25)

    result = engine.assess(
        intelligence=[
            make_intelligence(published_at=old_time)
        ],
        now=REFERENCE_TIME,
    )

    assert result.impacts == []


def test_recent_intelligence_has_stronger_impact_than_old_intelligence() -> None:
    engine = MarketImpactEngine(
        intelligence_max_age=timedelta(hours=24)
    )

    recent = make_intelligence(
        published_at=REFERENCE_TIME - timedelta(minutes=10)
    )

    old = make_intelligence(
        published_at=REFERENCE_TIME - timedelta(hours=20)
    )

    recent_result = engine.assess(
        intelligence=[recent],
        now=REFERENCE_TIME,
    )

    old_result = engine.assess(
        intelligence=[old],
        now=REFERENCE_TIME,
    )

    assert (
        recent_result.impacts[0].impact_score
        > old_result.impacts[0].impact_score
    )


def test_multiple_items_are_aggregated_by_symbol() -> None:
    engine = MarketImpactEngine()

    result = engine.assess(
        intelligence=[
            make_intelligence(
                direction=SignalDirection.LONG,
                impact_score=0.8,
            ),
            make_intelligence(
                direction=SignalDirection.LONG,
                impact_score=0.6,
            ),
        ],
        now=REFERENCE_TIME,
    )

    assert len(result.impacts) == 1
    assert result.impacts[0].symbol == "XAUUSD"
    assert result.impacts[0].news_count == 2
    assert result.impacts[0].direction is SignalDirection.LONG
    assert result.impacts[0].impact_score <= 1.0


def test_high_impact_event_increases_event_risk() -> None:
    engine = MarketImpactEngine()

    result = engine.assess(
        intelligence=[],
        events=[make_event(importance=0.9)],
        now=REFERENCE_TIME,
    )

    assert result.event_risk_score == 0.9
    assert result.high_impact_event_count == 1


def test_unconfirmed_event_does_not_create_event_risk() -> None:
    engine = MarketImpactEngine()

    result = engine.assess(
        intelligence=[],
        events=[make_event(importance=0.9, confirmed=False)],
        now=REFERENCE_TIME,
    )

    assert result.event_risk_score == 0.0
    assert result.high_impact_event_count == 0


def test_event_outside_risk_window_is_ignored() -> None:
    engine = MarketImpactEngine(
        intelligence_max_age=timedelta(hours=24)
    )

    result = engine.assess(
        intelligence=[],
        events=[
            make_event(
                importance=0.9,
                scheduled_at=REFERENCE_TIME + timedelta(hours=25),
            )
        ],
        now=REFERENCE_TIME,
    )

    assert result.event_risk_score == 0.0
    assert result.high_impact_event_count == 0


def test_context_contains_generated_time_and_rationale() -> None:
    engine = MarketImpactEngine()

    result = engine.assess(
        intelligence=[],
        now=REFERENCE_TIME,
    )

    assert result.generated_at == REFERENCE_TIME
    assert "symbols_assessed=0" in result.rationale
    assert "event_risk_score=0.000" in result.rationale


def test_time_decay_uses_published_at_field() -> None:
    engine = MarketImpactEngine(
        intelligence_max_age=timedelta(hours=24)
    )

    old = make_intelligence(
        published_at=REFERENCE_TIME - timedelta(hours=20)
    )

    result = engine.assess(
        intelligence=[old],
        now=REFERENCE_TIME,
    )

    impact = result.impacts[0]

    assert impact.impact_score < 0.8