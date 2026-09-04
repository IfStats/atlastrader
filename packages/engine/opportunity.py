from __future__ import annotations

from pydantic import BaseModel, Field

from packages.core.enums import SignalDirection
from packages.engine.market_context import MarketContext
from packages.intelligence.impact import SymbolImpact


class Opportunity(BaseModel):
    """Represents a candidate trading opportunity derived from market context."""

    symbol: str
    direction: SignalDirection
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    eligible: bool
    rationale: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)


class OpportunityEngine:
    """Evaluate whether a market context contains a tradeable opportunity."""

    _EPSILON: float = 1e-6

    def __init__(
        self,
        *,
        minimum_score: float = 0.30,
        minimum_confidence: float = 0.50,
        minimum_alignment: float = 0.25,
        maximum_event_risk: float = 0.70,
    ) -> None:
        for name, value in (
            ("minimum_score", minimum_score),
            ("minimum_confidence", minimum_confidence),
            ("minimum_alignment", minimum_alignment),
            ("maximum_event_risk", maximum_event_risk),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")

        self.minimum_score = minimum_score
        self.minimum_confidence = minimum_confidence
        self.minimum_alignment = minimum_alignment
        self.maximum_event_risk = maximum_event_risk

    def evaluate(self, context: MarketContext) -> Opportunity:
        """Evaluate a combined market context without executing a trade."""

        score = min(
            1.0,
            max(0.0, abs(context.combined_directional_score)),
        )
        confidence = min(
            1.0,
            max(0.0, context.combined_confidence),
        )
        event_risk = context.intelligence.event_risk_score

        rationale = [
            f"symbol={context.market_state.symbol}",
            f"direction={context.direction.value}",
            f"score={score:.3f}",
            f"confidence={confidence:.3f}",
            f"event_risk={event_risk:.3f}",
        ]

        rejection_reasons: list[str] = []

        if context.direction is SignalDirection.FLAT:
            rejection_reasons.append("direction_is_flat")

        if not context.is_tradeable:
            rejection_reasons.append("market_context_not_tradeable")

        if score < self.minimum_score:
            rejection_reasons.append(
                f"score_below_threshold:{self.minimum_score:.3f}"
            )

        if confidence < self.minimum_confidence:
            rejection_reasons.append(
                f"confidence_below_threshold:{self.minimum_confidence:.3f}"
            )

        intelligence_impact = self._get_intelligence_impact(context)

        if intelligence_impact is not None:
            if (
                intelligence_impact.direction is not SignalDirection.FLAT
                and intelligence_impact.direction is not context.direction
            ):
                rejection_reasons.append("technical_intelligence_conflict")
            else:
                alignment = self._calculate_alignment(
                    context,
                    intelligence_impact,
                )
                rationale.append(f"alignment={alignment:.3f}")

                if (
                    intelligence_impact.direction is not SignalDirection.FLAT
                    and alignment < self.minimum_alignment
                ):
                    rejection_reasons.append(
                        "technical_intelligence_alignment_below_threshold:"
                        f"{self.minimum_alignment:.3f}"
                    )
        else:
            rationale.append("alignment=no_symbol_intelligence")

        if event_risk > self.maximum_event_risk:
            rejection_reasons.append(
                f"event_risk_above_threshold:{self.maximum_event_risk:.3f}"
            )

        eligible = not rejection_reasons

        rationale.append(f"eligible={eligible}")

        return Opportunity(
            symbol=context.market_state.symbol,
            direction=(
                context.direction
                if eligible
                else SignalDirection.FLAT
            ),
            score=score,
            confidence=confidence,
            eligible=eligible,
            rationale=rationale,
            rejection_reasons=rejection_reasons,
        )

    @staticmethod
    def _get_intelligence_impact(
        context: MarketContext,
    ) -> SymbolImpact | None:
        """Return symbol-specific intelligence when available."""

        symbol = context.market_state.symbol

        return next(
            (
                impact
                for impact in context.intelligence.impacts
                if impact.symbol == symbol
            ),
            None,
        )

    @classmethod
    def _calculate_alignment(
        cls,
        context: MarketContext,
        intelligence_impact: SymbolImpact | None,
    ) -> float:
        """Measure agreement between technical and intelligence direction."""

        if intelligence_impact is None:
            return 0.0

        impact_direction = intelligence_impact.direction

        if impact_direction is SignalDirection.FLAT:
            return 0.0

        technical_score = (
            context.market_state.trend_score
            + context.market_state.momentum_score
        ) / 2.0

        technical_direction = cls._score_to_direction(technical_score)

        if technical_direction is SignalDirection.FLAT:
            return 0.0

        if technical_direction is not impact_direction:
            return 0.0

        return min(
            1.0,
            (
                abs(technical_score)
                + abs(intelligence_impact.directional_score)
            )
            / 2.0,
        )

    @classmethod
    def _score_to_direction(
        cls,
        score: float,
    ) -> SignalDirection:
        if score > cls._EPSILON:
            return SignalDirection.LONG

        if score < -cls._EPSILON:
            return SignalDirection.SHORT

        return SignalDirection.FLAT