from datetime import UTC, datetime
from decimal import Decimal

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
    if directional_score > 0:
        direction = SignalDirection.LONG
    elif directional_score < 0:
        direction = SignalDirection.SHORT
    else:
        direction = SignalDirection.FLAT

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


def test_market_state_and_impact_context_compose() -> None:
    engine = MarketContextEngine()

    market_state = make_market_state()
    intelligence = make_intelligence()

    context = engine.build(
        symbol="XAUUSD",
        market_state=market_state,
        intelligence=intelligence,
    )

    assert context.market_state == market_state
    assert context.intelligence == intelligence
    assert context.direction is SignalDirection.LONG
    assert context.combined_directional_score > 0
    assert context.combined_confidence > 0
    assert context.is_tradeable is True


def test_context_preserves_existing_market_state() -> None:
    engine = MarketContextEngine()

    market_state = make_market_state()
    original = market_state.model_copy(deep=True)

    intelligence = make_intelligence()

    context = engine.build(
        symbol="XAUUSD",
        market_state=market_state,
        intelligence=intelligence,
    )

    assert context.market_state == original
    assert market_state == original


def test_symbol_specific_intelligence_is_used() -> None:
    engine = MarketContextEngine()

    market_state = make_market_state()

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

    context = engine.build(
        symbol="XAUUSD",
        market_state=market_state,
        intelligence=intelligence,
    )

    assert context.direction is SignalDirection.LONG
    assert context.combined_directional_score > 0


def test_missing_symbol_intelligence_does_not_block_context() -> None:
    engine = MarketContextEngine()

    market_state = make_market_state()

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
            )
        ],
        event_risk_score=0.0,
        high_impact_event_count=0,
    )

    context = engine.build(
        symbol="XAUUSD",
        market_state=market_state,
        intelligence=intelligence,
    )

    assert context.direction is SignalDirection.LONG
    assert context.combined_directional_score == 0.42
    assert context.combined_confidence == 0.42


def test_external_event_risk_propagates_to_tradeability() -> None:
    engine = MarketContextEngine()

    context = engine.build(
        symbol="XAUUSD",
        market_state=make_market_state(),
        intelligence=make_intelligence(
            event_risk_score=1.0,
        ),
    )

    assert context.is_tradeable is False


def test_non_tradeable_market_state_remains_blocked() -> None:
    engine = MarketContextEngine()

    context = engine.build(
        symbol="XAUUSD",
        market_state=make_market_state(
            tradeable=False,
        ),
        intelligence=make_intelligence(),
    )

    assert context.is_tradeable is False