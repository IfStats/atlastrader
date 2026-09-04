from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.core.enums import MarketStatus, SignalDirection, Timeframe
from packages.core.models import MarketState
from packages.engine.market_context import MarketContext
from packages.engine.opportunity import OpportunityEngine
from packages.intelligence.impact import (
    MarketImpactContext,
    SymbolImpact,
)

REFERENCE_TIME = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def make_market_state(
    *,
    symbol: str = "XAUUSD",
    trend_score: float = 0.8,
    momentum_score: float = 0.6,
    tradeable: bool = True,
) -> MarketState:
    return MarketState(
        symbol=symbol,
        timestamp=REFERENCE_TIME,
        timeframe=Timeframe.M5,
        price=Decimal(4400),
        trend_score=trend_score,
        momentum_score=momentum_score,
        volatility_score=0.4,
        volatility=Decimal(10),
        spread=Decimal("0.5"),
        market_status=MarketStatus.OPEN,
        session="london",
        is_tradeable=tradeable,
    )


def make_context(
    *,
    combined_score: float = 0.7,
    confidence: float = 0.8,
    direction: SignalDirection = SignalDirection.LONG,
    tradeable: bool = True,
    intelligence_direction: SignalDirection = SignalDirection.LONG,
    intelligence_score: float = 0.8,
    event_risk: float = 0.0,
    trend_score: float = 0.8,
    momentum_score: float = 0.6,
) -> MarketContext:
    intelligence = MarketImpactContext(
        generated_at=REFERENCE_TIME,
        impacts=[
            SymbolImpact(
                symbol="XAUUSD",
                direction=intelligence_direction,
                directional_score=intelligence_score,
                impact_score=0.8,
                confidence=0.9,
                news_count=1,
            )
        ],
        event_risk_score=event_risk,
        high_impact_event_count=0,
    )

    return MarketContext(
        market_state=make_market_state(
            tradeable=tradeable,
            trend_score=trend_score,
            momentum_score=momentum_score,
        ),
        intelligence=intelligence,
        combined_directional_score=combined_score,
        combined_confidence=confidence,
        direction=direction,
        is_tradeable=tradeable,
    )


def test_strong_long_opportunity_is_eligible() -> None:
    engine = OpportunityEngine()

    opportunity = engine.evaluate(make_context())

    assert opportunity.eligible is True
    assert opportunity.direction is SignalDirection.LONG
    assert opportunity.score == 0.7
    assert opportunity.confidence == 0.8
    assert opportunity.rejection_reasons == []


def test_strong_short_opportunity_is_eligible() -> None:
    engine = OpportunityEngine()

    opportunity = engine.evaluate(
        make_context(
            combined_score=-0.7,
            direction=SignalDirection.SHORT,
            intelligence_direction=SignalDirection.SHORT,
            intelligence_score=-0.8,
            trend_score=-0.7,
            momentum_score=-0.7,
        )
    )

    assert opportunity.eligible is True
    assert opportunity.direction is SignalDirection.SHORT


def test_flat_direction_is_rejected() -> None:
    engine = OpportunityEngine()

    opportunity = engine.evaluate(
        make_context(
            combined_score=0.0,
            direction=SignalDirection.FLAT,
            intelligence_direction=SignalDirection.FLAT,
            intelligence_score=0.0,
        )
    )

    assert opportunity.eligible is False
    assert opportunity.direction is SignalDirection.FLAT
    assert "direction_is_flat" in opportunity.rejection_reasons


def test_low_score_is_rejected() -> None:
    engine = OpportunityEngine(minimum_score=0.30)

    opportunity = engine.evaluate(
        make_context(
            combined_score=0.20,
        )
    )

    assert opportunity.eligible is False
    assert "score_below_threshold:0.300" in opportunity.rejection_reasons


def test_low_confidence_is_rejected() -> None:
    engine = OpportunityEngine(minimum_confidence=0.50)

    opportunity = engine.evaluate(
        make_context(
            confidence=0.40,
        )
    )

    assert opportunity.eligible is False
    assert (
        "confidence_below_threshold:0.500"
        in opportunity.rejection_reasons
    )


def test_non_tradeable_context_is_rejected() -> None:
    engine = OpportunityEngine()

    opportunity = engine.evaluate(
        make_context(
            tradeable=False,
        )
    )

    assert opportunity.eligible is False
    assert "market_context_not_tradeable" in opportunity.rejection_reasons


def test_conflicting_intelligence_is_rejected() -> None:
    engine = OpportunityEngine()

    opportunity = engine.evaluate(
        make_context(
            direction=SignalDirection.LONG,
            intelligence_direction=SignalDirection.SHORT,
            intelligence_score=-0.8,
        )
    )

    assert opportunity.eligible is False
    assert "technical_intelligence_conflict" in opportunity.rejection_reasons
    assert opportunity.direction is SignalDirection.FLAT


def test_weak_alignment_is_rejected() -> None:
    engine = OpportunityEngine(minimum_alignment=0.25)

    opportunity = engine.evaluate(
        make_context(
            intelligence_score=0.05,
            trend_score=0.10,
            momentum_score=0.10,
        )
    )

    assert opportunity.eligible is False
    assert (
        "technical_intelligence_alignment_below_threshold:0.250"
        in opportunity.rejection_reasons
    )


def test_flat_intelligence_does_not_automatically_reject() -> None:
    engine = OpportunityEngine()

    opportunity = engine.evaluate(
        make_context(
            intelligence_direction=SignalDirection.FLAT,
            intelligence_score=0.0,
        )
    )

    assert opportunity.eligible is True
    assert opportunity.direction is SignalDirection.LONG


def test_excessive_event_risk_is_rejected() -> None:
    engine = OpportunityEngine(maximum_event_risk=0.70)

    opportunity = engine.evaluate(
        make_context(
            event_risk=0.80,
        )
    )

    assert opportunity.eligible is False
    assert (
        "event_risk_above_threshold:0.700"
        in opportunity.rejection_reasons
    )


def test_multiple_rejection_reasons_are_preserved() -> None:
    engine = OpportunityEngine(
        minimum_score=0.80,
        minimum_confidence=0.90,
        maximum_event_risk=0.50,
    )

    opportunity = engine.evaluate(
        make_context(
            combined_score=0.40,
            confidence=0.40,
            event_risk=0.80,
            tradeable=False,
        )
    )

    assert opportunity.eligible is False
    assert opportunity.direction is SignalDirection.FLAT

    assert "market_context_not_tradeable" in opportunity.rejection_reasons
    assert "score_below_threshold:0.800" in opportunity.rejection_reasons
    assert (
        "confidence_below_threshold:0.900"
        in opportunity.rejection_reasons
    )
    assert "event_risk_above_threshold:0.500" in opportunity.rejection_reasons


def test_missing_symbol_intelligence_is_handled_safely() -> None:
    market_state = make_market_state()

    intelligence = MarketImpactContext(
        generated_at=REFERENCE_TIME,
        impacts=[
            SymbolImpact(
                symbol="EURUSD",
                direction=SignalDirection.SHORT,
                directional_score=-0.8,
                impact_score=0.8,
                confidence=0.9,
                news_count=1,
            )
        ],
        event_risk_score=0.0,
        high_impact_event_count=0,
    )

    context = MarketContext(
        market_state=market_state,
        intelligence=intelligence,
        combined_directional_score=0.7,
        combined_confidence=0.8,
        direction=SignalDirection.LONG,
        is_tradeable=True,
    )

    opportunity = OpportunityEngine().evaluate(context)

    assert opportunity.eligible is True
    assert opportunity.direction is SignalDirection.LONG
    assert "alignment=no_symbol_intelligence" in opportunity.rationale


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("minimum_score", -0.1),
        ("minimum_score", 1.1),
        ("minimum_confidence", -0.1),
        ("minimum_confidence", 1.1),
        ("minimum_alignment", -0.1),
        ("minimum_alignment", 1.1),
        ("maximum_event_risk", -0.1),
        ("maximum_event_risk", 1.1),
    ],
)
def test_thresholds_must_be_between_zero_and_one(
    parameter: str,
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=f"{parameter} must be between 0 and 1",
    ):
        OpportunityEngine(**{parameter: value})