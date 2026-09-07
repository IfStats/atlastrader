from collections import defaultdict
from collections.abc import Callable

from packages.learning.models import (
    LearningRecord,
)
from packages.performance.engine import (
    PerformanceEngine,
)
from packages.performance.models import (
    PerformanceSummary,
    SegmentedPerformanceSummary,
)

UNSPECIFIED_SESSION = "__unspecified__"


class SegmentedPerformanceEngine:
    """Calculate performance across deterministic trade segments."""

    def __init__(
        self,
        *,
        performance_engine: PerformanceEngine | None = None,
    ) -> None:
        self.performance_engine = (
            performance_engine
            or PerformanceEngine()
        )

    def summarize(
        self,
        records: list[LearningRecord],
    ) -> SegmentedPerformanceSummary:
        """Return aggregate and segmented trading performance."""

        overall = (
            self.performance_engine.summarize(
                records
            )
        )

        return SegmentedPerformanceSummary(
            overall=overall,
            by_strategy=self._summarize_by(
                records,
                self._strategy_key,
            ),
            by_symbol=self._summarize_by(
                records,
                self._symbol_key,
            ),
            by_timeframe=self._summarize_by(
                records,
                self._timeframe_key,
            ),
            by_session=self._summarize_by(
                records,
                self._session_key,
            ),
        )

    def _summarize_by(
        self,
        records: list[LearningRecord],
        key_function: Callable[
            [LearningRecord],
            str,
        ],
    ) -> dict[
        str,
        PerformanceSummary,
    ]:
        groups: defaultdict[
            str,
            list[LearningRecord],
        ] = defaultdict(list)

        for record in records:
            key = key_function(
                record
            )

            groups[key].append(
                record
            )

        return {
            key: (
                self.performance_engine.summarize(
                    groups[key]
                )
            )
            for key in sorted(
                groups
            )
        }

    @staticmethod
    def _strategy_key(
        record: LearningRecord,
    ) -> str:
        return record.strategy.value

    @staticmethod
    def _symbol_key(
        record: LearningRecord,
    ) -> str:
        symbol = (
            record.symbol
            .strip()
            .upper()
        )

        if not symbol:
            raise ValueError(
                "Performance symbol "
                "must not be blank"
            )

        return symbol

    @staticmethod
    def _timeframe_key(
        record: LearningRecord,
    ) -> str:
        return record.timeframe.value

    @staticmethod
    def _session_key(
        record: LearningRecord,
    ) -> str:
        if record.session is None:
            return UNSPECIFIED_SESSION

        session = (
            record.session
            .strip()
            .lower()
        )

        return (
            session
            or UNSPECIFIED_SESSION
        )