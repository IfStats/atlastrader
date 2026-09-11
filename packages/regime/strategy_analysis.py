from collections import defaultdict

from packages.learning.models import (
    LearningRecord,
)
from packages.performance.engine import (
    PerformanceEngine,
)
from packages.regime.analysis import (
    RegimePatternAnalyzer,
)
from packages.regime.classifier import (
    MarketRegimeClassifier,
)
from packages.regime.models import (
    StrategyRegimePattern,
)


class StrategyRegimeAnalyzer:
    """Analyze strategy performance inside deterministic market regimes."""

    def __init__(
        self,
        *,
        classifier: (
            MarketRegimeClassifier | None
        ) = None,
        performance_engine: (
            PerformanceEngine | None
        ) = None,
        pattern_analyzer: (
            RegimePatternAnalyzer | None
        ) = None,
    ) -> None:
        self.classifier = (
            classifier
            or MarketRegimeClassifier()
        )

        self.performance_engine = (
            performance_engine
            or PerformanceEngine()
        )

        self.pattern_analyzer = (
            pattern_analyzer
            or RegimePatternAnalyzer()
        )

    def analyze(
        self,
        records: list[LearningRecord],
    ) -> list[StrategyRegimePattern]:
        """Return ranked strategy-regime performance patterns."""

        groups: defaultdict[
            tuple[str, str],
            list[LearningRecord],
        ] = defaultdict(list)

        for record in records:
            strategy = (
                record.strategy.value
            )

            regime = (
                self.classifier.classify(
                    record
                )
            )

            groups[
                (
                    strategy,
                    regime.key,
                )
            ].append(
                record
            )

        patterns = [
            self._build_pattern(
                strategy=strategy,
                regime_key=regime_key,
                records=groups[
                    (
                        strategy,
                        regime_key,
                    )
                ],
            )
            for (
                strategy,
                regime_key,
            ) in sorted(groups)
        ]

        return sorted(
            patterns,
            key=self._ranking_key,
            reverse=True,
        )

    def _build_pattern(
        self,
        *,
        strategy: str,
        regime_key: str,
        records: list[LearningRecord],
    ) -> StrategyRegimePattern:
        performance = (
            self.performance_engine.summarize(
                records
            )
        )

        sufficient_sample = (
            performance.total_trades
            >= (
                self.pattern_analyzer
                .MINIMUM_SAMPLE_SIZE
            )
        )

        return StrategyRegimePattern(
            strategy=strategy,
            regime_key=regime_key,
            sample_size=(
                performance.total_trades
            ),
            performance=performance,
            quality=(
                self.pattern_analyzer
                .classify_quality(
                    performance
                )
            ),
            sufficient_sample=(
                sufficient_sample
            ),
        )

    @staticmethod
    def _ranking_key(
        pattern: StrategyRegimePattern,
    ) -> tuple[
        bool,
        object,
        int,
        str,
    ]:
        return (
            pattern.sufficient_sample,
            pattern.performance.expectancy,
            pattern.sample_size,
            pattern.key,
        )