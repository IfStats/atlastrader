from __future__ import annotations

from pydantic import BaseModel, Field

from packages.core.enums import SignalDirection
from packages.core.models import MarketState
from packages.intelligence.impact import MarketImpactContext, SymbolImpact


class MarketContext(BaseModel):
    """Combined technical and external-intelligence market context."""

    market_state: MarketState
    intelligence: MarketImpactContext
    combined_directional_score: float = Field(ge=-1.0, le=1.0)
    combined_confidence: float = Field(ge=0.0, le=1.0)
    direction: SignalDirection
    is_tradeable: bool
    rationale: list[str] = Field(default_factory=list)


class MarketContextEngine:
    """Combine technical market state with symbol-specific intelligence."""

    def __init__(
        self,
        *,
        technical_weight: float = 0.60,
        intelligence_weight: float = 0.40,
    ) -> None:
        if technical_weight < 0.0:
            raise ValueError("technical_weight must be non-negative")

        if intelligence_weight < 0.0:
            raise ValueError("intelligence_weight must be non-negative")

        total_weight = technical_weight + intelligence_weight

        if total_weight <= 0.0:
            raise ValueError("At least one context weight must be positive")

        self.technical_weight = technical_weight / total_weight
        self.intelligence_weight = intelligence_weight / total_weight

    def build(
        self,
        *,
        symbol: str,
        market_state: MarketState,
        intelligence: MarketImpactContext,
    ) -> MarketContext:
        if market_state.symbol != symbol:
            raise ValueError(
                "symbol must match market_state.symbol"
            )

        intelligence_impact = self._get_symbol_impact(
            symbol=symbol,
            intelligence=intelligence,
        )

        technical_score = (
            market_state.trend_score
            + market_state.momentum_score
        ) / 2.0

        if intelligence_impact is None:
            intelligence_score = 0.0
            intelligence_confidence = 0.0
        else:
            intelligence_score = (
                intelligence_impact.directional_score
            )
            intelligence_confidence = (
                intelligence_impact.confidence
            )

        combined_score = (
            technical_score * self.technical_weight
            + intelligence_score * self.intelligence_weight
        )

        combined_score = max(-1.0, min(1.0, combined_score))

        combined_confidence = (
            abs(technical_score) * self.technical_weight
            + intelligence_confidence * self.intelligence_weight
        )

        combined_confidence = max(
            0.0,
            min(1.0, combined_confidence),
        )

        direction = self._score_to_direction(combined_score)

        is_tradeable = (
            market_state.is_tradeable
            and intelligence.event_risk_score < 1.0
        )

        rationale = [
            f"symbol={symbol}",
            f"technical_score={technical_score:.3f}",
            f"intelligence_score={intelligence_score:.3f}",
            f"combined_score={combined_score:.3f}",
            f"combined_confidence={combined_confidence:.3f}",
            f"event_risk_score={intelligence.event_risk_score:.3f}",
            f"is_tradeable={is_tradeable}",
        ]

        return MarketContext(
            market_state=market_state,
            intelligence=intelligence,
            combined_directional_score=combined_score,
            combined_confidence=combined_confidence,
            direction=direction,
            is_tradeable=is_tradeable,
            rationale=rationale,
        )

    @staticmethod
    def _get_symbol_impact(
        *,
        symbol: str,
        intelligence: MarketImpactContext,
    ) -> SymbolImpact | None:
        for impact in intelligence.impacts:
            if impact.symbol == symbol:
                return impact

        return None

    @staticmethod
    def _score_to_direction(score: float) -> SignalDirection:
        if score > 0:
            return SignalDirection.LONG

        if score < 0:
            return SignalDirection.SHORT

        return SignalDirection.FLAT