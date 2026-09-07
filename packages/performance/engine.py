from decimal import Decimal

from packages.learning.models import (
    LearningRecord,
)
from packages.performance.models import (
    PerformanceSummary,
)


class PerformanceEngine:
    """Calculate aggregate performance from learning records."""

    def summarize(
        self,
        records: list[LearningRecord],
    ) -> PerformanceSummary:
        """Return net-of-cost trading performance."""

        total_trades = len(
            records
        )

        winning_records = [
            record
            for record in records
            if record.net_pnl > Decimal(0)
        ]

        losing_records = [
            record
            for record in records
            if record.net_pnl < Decimal(0)
        ]

        breakeven_records = [
            record
            for record in records
            if record.net_pnl == Decimal(0)
        ]

        winning_trades = len(
            winning_records
        )
        losing_trades = len(
            losing_records
        )
        breakeven_trades = len(
            breakeven_records
        )

        total_net_pnl = sum(
            (
                record.net_pnl
                for record in records
            ),
            start=Decimal(0),
        )

        total_positive_net_pnl = sum(
            (
                record.net_pnl
                for record in winning_records
            ),
            start=Decimal(0),
        )

        total_negative_net_pnl = sum(
            (
                record.net_pnl
                for record in losing_records
            ),
            start=Decimal(0),
        )

        if total_trades == 0:
            return PerformanceSummary(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                breakeven_trades=0,
                win_rate=Decimal(0),
                loss_rate=Decimal(0),
                breakeven_rate=Decimal(0),
                total_net_pnl=Decimal(0),
                total_positive_net_pnl=Decimal(0),
                total_negative_net_pnl=Decimal(0),
                average_net_pnl=Decimal(0),
                average_win=Decimal(0),
                average_loss=Decimal(0),
                profit_factor=None,
                payoff_ratio=None,
                expectancy=Decimal(0),
            )

        trade_count = Decimal(
            total_trades
        )

        win_rate = (
            Decimal(winning_trades)
            / trade_count
        )

        loss_rate = (
            Decimal(losing_trades)
            / trade_count
        )

        breakeven_rate = (
            Decimal(breakeven_trades)
            / trade_count
        )

        average_net_pnl = (
            total_net_pnl
            / trade_count
        )

        average_win = (
            total_positive_net_pnl
            / Decimal(winning_trades)
            if winning_trades
            else Decimal(0)
        )

        average_loss = (
            total_negative_net_pnl
            / Decimal(losing_trades)
            if losing_trades
            else Decimal(0)
        )

        profit_factor = (
            total_positive_net_pnl
            / abs(
                total_negative_net_pnl
            )
            if total_negative_net_pnl
            < Decimal(0)
            else None
        )

        payoff_ratio = (
            average_win
            / abs(
                average_loss
            )
            if average_loss < Decimal(0)
            else None
        )

        expectancy = (
            win_rate
            * average_win
            + loss_rate
            * average_loss
        )

        return PerformanceSummary(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            breakeven_trades=breakeven_trades,
            win_rate=win_rate,
            loss_rate=loss_rate,
            breakeven_rate=breakeven_rate,
            total_net_pnl=total_net_pnl,
            total_positive_net_pnl=(
                total_positive_net_pnl
            ),
            total_negative_net_pnl=(
                total_negative_net_pnl
            ),
            average_net_pnl=average_net_pnl,
            average_win=average_win,
            average_loss=average_loss,
            profit_factor=profit_factor,
            payoff_ratio=payoff_ratio,
            expectancy=expectancy,
        )