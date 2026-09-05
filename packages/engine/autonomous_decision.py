from __future__ import annotations

from pydantic import BaseModel

from packages.core.enums import SignalDirection
from packages.engine.decision import AuthorizationDecision, DecisionEngine
from packages.engine.market_context import MarketContext
from packages.engine.opportunity import Opportunity, OpportunityEngine


class AutonomousDecision(BaseModel):
    """Complete autonomous evaluation from market context to authorization."""

    opportunity: Opportunity
    authorization: AuthorizationDecision

    @property
    def approved(self) -> bool:
        return self.authorization.approved

    @property
    def decision(self) -> SignalDirection:
        return self.authorization.decision


class AutonomousDecisionEngine:
    """Coordinate opportunity evaluation and autonomous authorization."""

    def __init__(
        self,
        *,
        opportunity_engine: OpportunityEngine | None = None,
        decision_engine: DecisionEngine | None = None,
    ) -> None:
        self.opportunity_engine = opportunity_engine or OpportunityEngine()
        self.decision_engine = decision_engine or DecisionEngine()

    def evaluate(
        self,
        context: MarketContext,
    ) -> AutonomousDecision:
        """Evaluate market context without executing a trade."""

        opportunity = self.opportunity_engine.evaluate(context)
        authorization = self.decision_engine.decide(opportunity)

        return AutonomousDecision(
            opportunity=opportunity,
            authorization=authorization,
        )