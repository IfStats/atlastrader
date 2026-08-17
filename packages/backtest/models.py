from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from packages.core.enums import SignalDirection


class BacktestConfig(BaseModel):
    """Configuration for a historical backtest."""

    symbol: str
    initial_balance: Decimal = Field(gt=0)
    commission_per_trade: Decimal = Field(
        default=Decimal(0),
        ge=0,
    )
    slippage: Decimal = Field(
        default=Decimal(0),
        ge=0,
    )
    spread: Decimal = Field(
        default=Decimal(0),
        ge=0,
    )
    contract_size: Decimal = Field(
        default=Decimal(1),
        gt=0,
    )


class BacktestTrade(BaseModel):
    """A simulated historical trade."""

    symbol: str
    direction: SignalDirection
    quantity: Decimal = Field(gt=0)

    entry_price: Decimal = Field(gt=0)
    exit_price: Decimal = Field(gt=0)

    profit_loss: Decimal
    commission: Decimal = Field(default=Decimal(0), ge=0)

    entry_time: datetime
    exit_time: datetime


class BacktestResult(BaseModel):
    """Aggregate results from a backtest."""

    initial_balance: Decimal
    ending_balance: Decimal
    total_profit: Decimal

    total_trades: int = Field(ge=0)
    winning_trades: int = Field(ge=0)
    losing_trades: int = Field(ge=0)

    max_drawdown: Decimal = Field(ge=0)

    trades: list[BacktestTrade] = Field(default_factory=list)

    @property
    def return_percentage(self) -> Decimal:
        if self.initial_balance == 0:
            return Decimal(0)

        return (
            self.total_profit / self.initial_balance
        ) * Decimal(100)

    @property
    def win_rate(self) -> Decimal:
        if self.total_trades == 0:
            return Decimal(0)

        return (
            Decimal(self.winning_trades)
            / Decimal(self.total_trades)
        ) * Decimal(100)