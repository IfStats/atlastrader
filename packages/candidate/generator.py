from datetime import UTC, datetime
from hashlib import sha256

from packages.candidate.models import (
    CandidateStrategy,
    CandidateStrategyStatus,
)
from packages.regime.models import (
    StrategyRegimePattern,
)
from packages.regime.promotion import (
    RegimePromotionEvaluator,
)


class CandidateStrategyGenerator:
    """Generate research candidates from strategy-regime evidence."""

    def __init__(
        self,
        *,
        promotion_evaluator: (
            RegimePromotionEvaluator | None
        ) = None,
    ) -> None:
        self.promotion_evaluator = (
            promotion_evaluator
            or RegimePromotionEvaluator()
        )

    def generate(
        self,
        pattern: StrategyRegimePattern,
        *,
        created_at: datetime | None = None,
    ) -> CandidateStrategy:
        """Create one deterministic candidate from a strategy-regime pattern."""

        eligibility = (
            self.promotion_evaluator.evaluate(
                pattern
            )
        )

        if eligibility.eligible:
            status = (
                CandidateStrategyStatus
                .ELIGIBLE_FOR_VALIDATION
            )

            rationale = [
                "promotion_gate_passed"
            ]

        else:
            status = (
                CandidateStrategyStatus
                .REJECTED
            )

            rationale = list(
                eligibility.rejection_reasons
            )

        timestamp = (
            created_at
            if created_at is not None
            else datetime.now(UTC)
        )

        return CandidateStrategy(
            id=self._candidate_id(
                pattern.key
            ),
            source_pattern_key=(
                pattern.key
            ),
            strategy=pattern.strategy,
            regime_key=pattern.regime_key,
            sample_size=pattern.sample_size,
            expectancy=(
                pattern.performance.expectancy
            ),
            win_rate=(
                pattern.performance.win_rate
            ),
            profit_factor=(
                pattern.performance.profit_factor
            ),
            payoff_ratio=(
                pattern.performance.payoff_ratio
            ),
            status=status,
            rationale=rationale,
            created_at=timestamp,
        )

    @staticmethod
    def _candidate_id(
        pattern_key: str,
    ) -> str:
        """Return stable candidate identity derived from source evidence."""
        digest = sha256(
            pattern_key.encode(
                "utf-8"
            )
        ).hexdigest()

        return (
            "candidate-"
            f"{digest[:16]}"
        )