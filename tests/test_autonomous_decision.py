from datetime import UTC, datetime
from decimal import Decimal

from packages.core.enums import MarketStatus, SignalDirection, Timeframe
from packages.core.models import MarketState
from packages.engine.autonomous_decision import AutonomousDecisionEngine
from packages.engine.market_context import MarketContext
from packages.engine.opportunity import OpportunityEngine
from packages.intelligence.impact import MarketImpactContext, SymbolImpact

REFERENCE_TIME = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)


def make_context(
    *,
    combined_score: float = 0.70,
    confidence: float = 0.80,
    direction: SignalDirection = SignalDirection.LONG,
    intelligence_direction: SignalDirection = SignalDirection.LONG,
    intelligence_score: float = 0.80,
    event_risk: float = 0.0,
    tradeable: bool = True,
    trend_score: float = 0.80,
    momentum_score: float = 0.60,
) -> MarketContext:
    market_state = MarketState(
        symbol="XAUUSD",
        timestamp=REFERENCE_TIME,
        timeframe=Timeframe.M5,
        price=Decimal(4400),
        trend_score=trend_score,
        momentum_score=momentum_score,
        volatility_score=0.40,
        volatility=Decimal(10),
        spread=Decimal("0.5"),
        market_status=MarketStatus.OPEN,
        session="london",
        is_tradeable=tradeable,
    )

    intelligence = MarketImpactContext(
        generated_at=REFERENCE_TIME,
        impacts=[
            SymbolImpact(
                symbol="XAUUSD",
                direction=intelligence_direction,
                directional_score=intelligence_score,
                impact_score=0.80,
                confidence=0.90,
                news_count=1,
            )
        ],
        event_risk_score=event_risk,
        high_impact_event_count=0,
    )

    return MarketContext(
        market_state=market_state,
        intelligence=intelligence,
        combined_directional_score=combined_score,
        combined_confidence=confidence,
        direction=direction,
        is_tradeable=tradeable,
    )


def test_strong_long_context_is_authorized() -> None:
    engine = AutonomousDecisionEngine()

    result = engine.evaluate(make_context())

    assert result.approved is True
    assert result.decision is SignalDirection.LONG
    assert result.opportunity.eligible is True
    assert result.authorization.approved is True


def test_strong_short_context_is_authorized() -> None:
    engine = AutonomousDecisionEngine()

    result = engine.evaluate(
        make_context(
            combined_score=-0.70,
            direction=SignalDirection.SHORT,
            intelligence_direction=SignalDirection.SHORT,
            intelligence_score=-0.80,
            trend_score=-0.70,
            momentum_score=-0.70,
        )
    )

    assert result.approved is True
    assert result.decision is SignalDirection.SHORT
    assert result.opportunity.eligible is True


def test_flat_context_is_rejected() -> None:
    engine = AutonomousDecisionEngine()

    result = engine.evaluate(
        make_context(
            combined_score=0.0,
            direction=SignalDirection.FLAT,
            intelligence_direction=SignalDirection.FLAT,
            intelligence_score=0.0,
        )
    )

    assert result.approved is False
    assert result.decision is SignalDirection.FLAT
    assert result.opportunity.eligible is False
    assert "direction_is_flat" in result.authorization.rejection_reasons


def test_conflicting_intelligence_is_rejected() -> None:
    engine = AutonomousDecisionEngine()

    result = engine.evaluate(
        make_context(
            intelligence_direction=SignalDirection.SHORT,
            intelligence_score=-0.80,
        )
    )

    assert result.approved is False
    assert result.decision is SignalDirection.FLAT
    assert "technical_intelligence_conflict" in (
        result.opportunity.rejection_reasons
    )


def test_excessive_event_risk_is_rejected() -> None:
    engine = AutonomousDecisionEngine()

    result = engine.evaluate(
        make_context(event_risk=0.90)
    )

    assert result.approved is False
    assert result.decision is SignalDirection.FLAT
    assert any(
        reason.startswith("event_risk_above_threshold:")
        for reason in result.opportunity.rejection_reasons
    )


def test_non_tradeable_context_is_rejected() -> None:
    engine = AutonomousDecisionEngine()

    result = engine.evaluate(
        make_context(tradeable=False)
    )

    assert result.approved is False
    assert result.decision is SignalDirection.FLAT
    assert "market_context_not_tradeable" in (
        result.opportunity.rejection_reasons
    )


def test_custom_engines_are_used() -> None:
    opportunity_engine = OpportunityEngine(
        minimum_score=0.90,
    )
    engine = AutonomousDecisionEngine(
        opportunity_engine=opportunity_engine,
    )

    result = engine.evaluate(make_context())

    assert result.approved is False
    assert result.decision is SignalDirection.FLAT
    assert "score_below_threshold:0.900" in (
        result.authorization.rejection_reasons
    )