from __future__ import annotations

from pydantic import BaseModel, Field

from packages.core.enums import SignalDirection
from packages.engine.opportunity import Opportunity


class AuthorizationDecision(BaseModel):
    """Represents the autonomous authorization decision for an opportunity."""

    symbol: str
    decision: SignalDirection
    approved: bool
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)


class DecisionEngine:
    """Authorize or reject a validated trading opportunity."""

    def __init__(
        self,
        *,
        minimum_score: float = 0.30,
        minimum_confidence: float = 0.50,
    ) -> None:
        for name, value in (
            ("minimum_score", minimum_score),
            ("minimum_confidence", minimum_confidence),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")

        self.minimum_score = minimum_score
        self.minimum_confidence = minimum_confidence

    def decide(self, opportunity: Opportunity) -> AuthorizationDecision:
        """Authorize an eligible opportunity without executing a trade."""

        rejection_reasons = list(opportunity.rejection_reasons)

        if not opportunity.eligible and not rejection_reasons:
            rejection_reasons.append("opportunity_not_eligible")

        if opportunity.score < self.minimum_score:
            rejection_reasons.append(
                f"score_below_threshold:{self.minimum_score:.3f}"
            )

        if opportunity.confidence < self.minimum_confidence:
            rejection_reasons.append(
                f"confidence_below_threshold:{self.minimum_confidence:.3f}"
            )

        approved = not rejection_reasons

        rationale = [
            f"symbol={opportunity.symbol}",
            f"opportunity_direction={opportunity.direction.value}",
            f"score={opportunity.score:.3f}",
            f"confidence={opportunity.confidence:.3f}",
            f"approved={approved}",
        ]

        return AuthorizationDecision(
            symbol=opportunity.symbol,
            decision=(
                opportunity.direction
                if approved
                else SignalDirection.FLAT
            ),
            approved=approved,
            score=opportunity.score,
            confidence=opportunity.confidence,
            rationale=rationale,
            rejection_reasons=rejection_reasons,
        )