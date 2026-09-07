from decimal import Decimal

from packages.learning.models import (
    LearningRecord,
)
from packages.performance.models import (
    PathPerformanceSummary,
)


class PathPerformanceEngine:
    """Calculate path-dependent realized trading statistics."""

    def summarize(
        self,
        records: list[LearningRecord],
    ) -> PathPerformanceSummary:
        """Calculate drawdown and streaks in deterministic close order."""

        ordered_records = sorted(
            records,
            key=lambda record: (
                record.closed_at,
                record.decision_timestamp,
                record.decision_id,
            ),
        )

        if not ordered_records:
            return PathPerformanceSummary(
                total_trades=0,
                ending_cumulative_pnl=Decimal(0),
                peak_cumulative_pnl=Decimal(0),
                minimum_cumulative_pnl=Decimal(0),
                max_drawdown=Decimal(0),
                max_drawdown_peak_pnl=Decimal(0),
                max_drawdown_trough_pnl=Decimal(0),
                max_consecutive_wins=0,
                max_consecutive_losses=0,
                max_consecutive_breakevens=0,
                ending_win_streak=0,
                ending_loss_streak=0,
                ending_breakeven_streak=0,
            )

        cumulative_pnl = Decimal(0)

        peak_cumulative_pnl = Decimal(0)
        minimum_cumulative_pnl = Decimal(0)

        max_drawdown = Decimal(0)
        max_drawdown_peak_pnl = Decimal(0)
        max_drawdown_trough_pnl = Decimal(0)

        current_wins = 0
        current_losses = 0
        current_breakevens = 0

        max_wins = 0
        max_losses = 0
        max_breakevens = 0

        for record in ordered_records:
            cumulative_pnl += record.net_pnl

            peak_cumulative_pnl = max(peak_cumulative_pnl, cumulative_pnl)

            minimum_cumulative_pnl = min(minimum_cumulative_pnl, cumulative_pnl)

            drawdown = (
                peak_cumulative_pnl
                - cumulative_pnl
            )

            if drawdown > max_drawdown:
                max_drawdown = drawdown
                max_drawdown_peak_pnl = (
                    peak_cumulative_pnl
                )
                max_drawdown_trough_pnl = (
                    cumulative_pnl
                )

            if record.net_pnl > Decimal(0):
                current_wins += 1
                current_losses = 0
                current_breakevens = 0

                max_wins = max(
                    max_wins,
                    current_wins,
                )

            elif record.net_pnl < Decimal(0):
                current_losses += 1
                current_wins = 0
                current_breakevens = 0

                max_losses = max(
                    max_losses,
                    current_losses,
                )

            else:
                current_breakevens += 1
                current_wins = 0
                current_losses = 0

                max_breakevens = max(
                    max_breakevens,
                    current_breakevens,
                )

        return PathPerformanceSummary(
            total_trades=len(
                ordered_records
            ),
            ending_cumulative_pnl=(
                cumulative_pnl
            ),
            peak_cumulative_pnl=(
                peak_cumulative_pnl
            ),
            minimum_cumulative_pnl=(
                minimum_cumulative_pnl
            ),
            max_drawdown=max_drawdown,
            max_drawdown_peak_pnl=(
                max_drawdown_peak_pnl
            ),
            max_drawdown_trough_pnl=(
                max_drawdown_trough_pnl
            ),
            max_consecutive_wins=max_wins,
            max_consecutive_losses=max_losses,
            max_consecutive_breakevens=(
                max_breakevens
            ),
            ending_win_streak=(
                current_wins
            ),
            ending_loss_streak=(
                current_losses
            ),
            ending_breakeven_streak=(
                current_breakevens
            ),
        )