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