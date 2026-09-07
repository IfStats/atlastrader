from decimal import Decimal
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class PerformanceSummary(BaseModel):
    """Immutable aggregate trading-performance summary."""

    model_config = ConfigDict(
        frozen=True
    )

    total_trades: int = Field(
        ge=0
    )
    winning_trades: int = Field(
        ge=0
    )
    losing_trades: int = Field(
        ge=0
    )
    breakeven_trades: int = Field(
        ge=0
    )

    win_rate: Decimal = Field(
        ge=0,
        le=1,
    )
    loss_rate: Decimal = Field(
        ge=0,
        le=1,
    )
    breakeven_rate: Decimal = Field(
        ge=0,
        le=1,
    )

    total_net_pnl: Decimal

    total_positive_net_pnl: Decimal = Field(
        ge=0
    )
    total_negative_net_pnl: Decimal = Field(
        le=0
    )

    average_net_pnl: Decimal
    average_win: Decimal = Field(
        ge=0
    )
    average_loss: Decimal = Field(
        le=0
    )

    profit_factor: Decimal | None = Field(
        default=None,
        ge=0,
    )
    payoff_ratio: Decimal | None = Field(
        default=None,
        ge=0,
    )

    expectancy: Decimal

    @model_validator(
        mode="after"
    )
    def validate_counts(
        self,
    ) -> Self:
        classified = (
            self.winning_trades
            + self.losing_trades
            + self.breakeven_trades
        )

        if classified != self.total_trades:
            raise ValueError(
                "Performance trade counts "
                "must equal total_trades"
            )
        return self

class SegmentedPerformanceSummary(BaseModel):
    """Performance summaries partitioned by trading dimensions."""

    model_config = ConfigDict(
        frozen=True
    )

    overall: PerformanceSummary

    by_strategy: dict[
        str,
        PerformanceSummary,
    ] = Field(
        default_factory=dict
    )

    by_symbol: dict[
        str,
        PerformanceSummary,
    ] = Field(
        default_factory=dict
    )

    by_timeframe: dict[
        str,
        PerformanceSummary,
    ] = Field(
        default_factory=dict
    )

    by_session: dict[
        str,
        PerformanceSummary,
    ] = Field(
        default_factory=dict
    )

    @model_validator(
        mode="after"
    )
    def validate_segment_totals(
        self,
    ) -> Self:
        dimensions = (
            (
                "strategy",
                self.by_strategy,
            ),
            (
                "symbol",
                self.by_symbol,
            ),
            (
                "timeframe",
                self.by_timeframe,
            ),
            (
                "session",
                self.by_session,
            ),
        )

        for (
            dimension,
            summaries,
        ) in dimensions:
            segmented_total = sum(
                (
                    summary.total_trades
                    for summary
                    in summaries.values()
                ),
                start=0,
            )

            if (
                segmented_total
                != self.overall.total_trades
            ):
                raise ValueError(
                    f"{dimension} segment totals "
                    "must equal overall total"
                )

        return self

class PathPerformanceSummary(BaseModel):
    """Immutable path-dependent realized-performance statistics."""

    model_config = ConfigDict(
        frozen=True
    )

    total_trades: int = Field(
        ge=0
    )

    ending_cumulative_pnl: Decimal
    peak_cumulative_pnl: Decimal
    minimum_cumulative_pnl: Decimal

    max_drawdown: Decimal = Field(
        ge=0
    )

    max_drawdown_peak_pnl: Decimal
    max_drawdown_trough_pnl: Decimal

    max_consecutive_wins: int = Field(
        ge=0
    )
    max_consecutive_losses: int = Field(
        ge=0
    )
    max_consecutive_breakevens: int = Field(
        ge=0
    )

    ending_win_streak: int = Field(
        ge=0
    )
    ending_loss_streak: int = Field(
        ge=0
    )
    ending_breakeven_streak: int = Field(
        ge=0
    )

    @model_validator(
        mode="after"
    )
    def validate_path_statistics(
        self,
    ) -> Self:
        expected_drawdown = (
            self.max_drawdown_peak_pnl
            - self.max_drawdown_trough_pnl
        )

        if expected_drawdown != self.max_drawdown:
            raise ValueError(
                "max_drawdown must equal "
                "peak minus trough"
            )

        streaks = (
            self.max_consecutive_wins,
            self.max_consecutive_losses,
            self.max_consecutive_breakevens,
            self.ending_win_streak,
            self.ending_loss_streak,
            self.ending_breakeven_streak,
        )

        if any(
            streak > self.total_trades
            for streak in streaks
        ):
            raise ValueError(
                "Performance streak cannot "
                "exceed total_trades"
            )

        return self    