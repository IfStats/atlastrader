from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.core.enums import MarketStatus, SignalDirection, Timeframe
from packages.core.models import MarketState
from packages.engine.market_context import MarketContextEngine
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


def make_intelligence(
    *,
    symbol: str = "XAUUSD",
    directional_score: float = 0.7,
    impact_score: float = 0.8,
    confidence: float = 0.9,
    event_risk_score: float = 0.0,
) -> MarketImpactContext:
    direction = SignalDirection.FLAT

    if directional_score > 0:
        direction = SignalDirection.LONG
    elif directional_score < 0:
        direction = SignalDirection.SHORT

    return MarketImpactContext(
        generated_at=REFERENCE_TIME,
        impacts=[
            SymbolImpact(
                symbol=symbol,
                direction=direction,
                directional_score=directional_score,
                impact_score=impact_score,
                confidence=confidence,
                news_count=1,
            )
        ],
        event_risk_score=event_risk_score,
        high_impact_event_count=0,
    )


def test_combines_technical_and_intelligence_scores() -> None:
    engine = MarketContextEngine()

    result = engine.build(
        symbol="XAUUSD",
        market_state=make_market_state(),
        intelligence=make_intelligence(),
    )

    assert result.direction is SignalDirection.LONG
    assert result.combined_directional_score > 0
    assert result.combined_confidence > 0
    assert result.is_tradeable is True


def test_negative_combined_context_produces_short() -> None:
    engine = MarketContextEngine()

    result = engine.build(
        symbol="XAUUSD",
        market_state=make_market_state(
            trend_score=-0.8,
            momentum_score=-0.6,
        ),
        intelligence=make_intelligence(
            directional_score=-0.7,
        ),
    )

    assert result.direction is SignalDirection.SHORT
    assert result.combined_directional_score < 0


def test_no_intelligence_preserves_technical_direction() -> None:
    engine = MarketContextEngine()

    intelligence = MarketImpactContext(
        generated_at=REFERENCE_TIME,
        impacts=[],
        event_risk_score=0.0,
        high_impact_event_count=0,
    )

    result = engine.build(
        symbol="XAUUSD",
        market_state=make_market_state(),
        intelligence=intelligence,
    )

    assert result.direction is SignalDirection.LONG
    assert result.combined_directional_score > 0


def test_non_tradeable_market_remains_non_tradeable() -> None:
    engine = MarketContextEngine()

    result = engine.build(
        symbol="XAUUSD",
        market_state=make_market_state(tradeable=False),
        intelligence=make_intelligence(),
    )

    assert result.is_tradeable is False


def test_extreme_event_risk_blocks_tradeability() -> None:
    engine = MarketContextEngine()

    result = engine.build(
        symbol="XAUUSD",
        market_state=make_market_state(),
        intelligence=make_intelligence(event_risk_score=1.0),
    )

    assert result.is_tradeable is False


def test_custom_weights_are_normalized() -> None:
    engine = MarketContextEngine(
        technical_weight=3.0,
        intelligence_weight=1.0,
    )

    result = engine.build(
        symbol="XAUUSD",
        market_state=make_market_state(),
        intelligence=make_intelligence(),
    )

    expected = (0.7 * 0.75) + (0.7 * 0.25)

    assert result.combined_directional_score == pytest.approx(expected)


def test_invalid_weights_are_rejected() -> None:
    with pytest.raises(ValueError, match="At least one context weight"):
        MarketContextEngine(
            technical_weight=0.0,
            intelligence_weight=0.0,
        )


def test_symbol_specific_intelligence_is_selected() -> None:
    engine = MarketContextEngine()

    intelligence = MarketImpactContext(
        generated_at=REFERENCE_TIME,
        impacts=[
            SymbolImpact(
                symbol="EURUSD",
                direction=SignalDirection.SHORT,
                directional_score=-1.0,
                impact_score=1.0,
                confidence=1.0,
                news_count=1,
            ),
            SymbolImpact(
                symbol="XAUUSD",
                direction=SignalDirection.LONG,
                directional_score=0.5,
                impact_score=0.5,
                confidence=0.8,
                news_count=1,
            ),
        ],
        event_risk_score=0.0,
        high_impact_event_count=0,
    )

    result = engine.build(
        symbol="XAUUSD",
        market_state=make_market_state(),
        intelligence=intelligence,
    )

    assert result.direction is SignalDirection.LONG
    assert result.combined_directional_score > 0


def test_mismatched_symbol_is_rejected() -> None:
    engine = MarketContextEngine()

    with pytest.raises(
        ValueError,
        match="symbol must match market_state.symbol",
    ):
        engine.build(
            symbol="EURUSD",
            market_state=make_market_state(symbol="XAUUSD"),
            intelligence=make_intelligence(symbol="EURUSD"),
        )


def test_neutral_context_produces_flat_direction() -> None:
    engine = MarketContextEngine()

    result = engine.build(
        symbol="XAUUSD",
        market_state=make_market_state(
            trend_score=0.0,
            momentum_score=0.0,
        ),
        intelligence=make_intelligence(
            directional_score=0.0,
            confidence=0.0,
        ),
    )

    assert result.direction is SignalDirection.FLAT
    assert result.combined_directional_score == 0.0


def test_rationale_contains_context_components() -> None:
    engine = MarketContextEngine()

    result = engine.build(
        symbol="XAUUSD",
        market_state=make_market_state(),
        intelligence=make_intelligence(),
    )

    assert "symbol=XAUUSD" in result.rationale[0]
    assert "technical_score=" in result.rationale[1]
    assert "intelligence_score=" in result.rationale[2]
    assert "combined_score=" in result.rationale[3]
    assert "combined_confidence=" in result.rationale[4]
    assert "event_risk_score=" in result.rationale[5]
    assert "is_tradeable=" in result.rationale[6]