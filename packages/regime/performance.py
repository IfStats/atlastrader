from collections import defaultdict

from packages.learning.models import (
    LearningRecord,
)
from packages.performance.engine import (
    PerformanceEngine,
)
from packages.regime.classifier import (
    MarketRegimeClassifier,
)
from packages.regime.models import (
    RegimePerformanceSummary,
)


class RegimePerformanceEngine:
    """Calculate trading performance across deterministic market regimes."""

    def __init__(
        self,
        *,
        classifier: (
            MarketRegimeClassifier | None
        ) = None,
        performance_engine: (
            PerformanceEngine | None
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

    def summarize(
        self,
        records: list[LearningRecord],
    ) -> RegimePerformanceSummary:
        """Return overall and regime-partitioned performance."""

        overall = (
            self.performance_engine.summarize(
                records
            )
        )

        groups: defaultdict[
            str,
            list[LearningRecord],
        ] = defaultdict(list)

        for record in records:
            regime = (
                self.classifier.classify(
                    record
                )
            )

            groups[
                regime.key
            ].append(
                record
            )

        by_regime = {
            key: (
                self.performance_engine.summarize(
                    groups[key]
                )
            )
            for key in sorted(groups)
        }

        return RegimePerformanceSummary(
            overall=overall,
            by_regime=by_regime,
        )