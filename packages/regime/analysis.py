from packages.performance.models import (
    PerformanceSummary,
)
from packages.regime.models import (
    RegimePattern,
    RegimePerformanceSummary,
    RegimeQuality,
)


class RegimePatternAnalyzer:
    """Evaluate deterministic regime-performance quality."""

    MINIMUM_SAMPLE_SIZE = 10

    STRONG_PROFIT_FACTOR = 1.50
    POSITIVE_PROFIT_FACTOR = 1.10
    POOR_PROFIT_FACTOR = 0.80

    def analyze(
        self,
        summary: RegimePerformanceSummary,
    ) -> list[RegimePattern]:
        """Return ranked regime-performance patterns."""
        patterns = [
            self._build_pattern(
                regime_key=regime_key,
                performance=performance,
            )
            for (
                regime_key,
                performance,
            ) in summary.by_regime.items()
        ]

        return sorted(
            patterns,
            key=self._ranking_key,
            reverse=True,
        )

    def classify_quality(
        self,
        performance: PerformanceSummary,
    ) -> RegimeQuality:
        """Classify performance using deterministic evidence rules."""
        sufficient_sample = (
            performance.total_trades
            >= self.MINIMUM_SAMPLE_SIZE
        )

        if not sufficient_sample:
            return RegimeQuality.INCONCLUSIVE

        profit_factor = (
            performance.profit_factor
        )

        if (
            performance.expectancy > 0
            and profit_factor is not None
            and profit_factor
            >= self.STRONG_PROFIT_FACTOR
        ):
            return RegimeQuality.STRONG

        if (
            performance.expectancy > 0
            and (
                profit_factor is None
                or profit_factor
                >= self.POSITIVE_PROFIT_FACTOR
            )
        ):
            return RegimeQuality.POSITIVE

        if (
            performance.expectancy < 0
            and profit_factor is not None
            and profit_factor
            <= self.POOR_PROFIT_FACTOR
        ):
            return RegimeQuality.POOR

        if performance.expectancy < 0:
            return RegimeQuality.NEGATIVE

        return RegimeQuality.INCONCLUSIVE

    def _build_pattern(
        self,
        *,
        regime_key: str,
        performance: PerformanceSummary,
    ) -> RegimePattern:
        sufficient_sample = (
            performance.total_trades
            >= self.MINIMUM_SAMPLE_SIZE
        )

        return RegimePattern(
            regime_key=regime_key,
            sample_size=(
                performance.total_trades
            ),
            performance=performance,
            quality=self.classify_quality(
                performance
            ),
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
            sufficient_sample=(
                sufficient_sample
            ),
        )

    @staticmethod
    def _ranking_key(
        pattern: RegimePattern,
    ) -> tuple[
        bool,
        object,
        int,
    ]:
        return (
            pattern.sufficient_sample,
            pattern.expectancy,
            pattern.sample_size,
        )