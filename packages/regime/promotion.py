from decimal import Decimal
from typing import ClassVar

from packages.regime.models import (
    PromotionEligibility,
    RegimeQuality,
    StrategyRegimePattern,
)


class RegimePromotionEvaluator:
    """Evaluate whether a strategy-regime pattern can become a candidate."""

    MINIMUM_SAMPLE_SIZE = 30

    MINIMUM_PROFIT_FACTOR = Decimal(
        "1.20"
    )

    ALLOWED_QUALITIES: ClassVar[
    frozenset[RegimeQuality]
    ] = frozenset(
    {
        RegimeQuality.STRONG,
        RegimeQuality.POSITIVE,
    }
)

    def evaluate(
        self,
        pattern: StrategyRegimePattern,
    ) -> PromotionEligibility:
        """Return deterministic promotion eligibility."""

        rejection_reasons: list[str] = []

        performance = (
            pattern.performance
        )

        if (
            pattern.sample_size
            < self.MINIMUM_SAMPLE_SIZE
        ):
            rejection_reasons.append(
                "insufficient_sample_size"
            )

        if (
            pattern.quality
            not in self.ALLOWED_QUALITIES
        ):
            rejection_reasons.append(
                "unsupported_quality"
            )

        if (
            performance.expectancy
            <= Decimal(0)
        ):
            rejection_reasons.append(
                "non_positive_expectancy"
            )

        if (
            performance.profit_factor
            is None
        ):
            rejection_reasons.append(
                "missing_profit_factor"
            )

        elif (
            performance.profit_factor
            < self.MINIMUM_PROFIT_FACTOR
        ):
            rejection_reasons.append(
                "profit_factor_below_threshold"
            )

        eligible = (
            not rejection_reasons
        )

        return PromotionEligibility(
            pattern_key=pattern.key,
            eligible=eligible,
            sample_size=pattern.sample_size,
            quality=pattern.quality,
            expectancy=(
                performance.expectancy
            ),
            win_rate=(
                performance.win_rate
            ),
            profit_factor=(
                performance.profit_factor
            ),
            payoff_ratio=(
                performance.payoff_ratio
            ),
            rejection_reasons=(
                rejection_reasons
            ),
        )