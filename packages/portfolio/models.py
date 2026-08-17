from decimal import Decimal

from pydantic import BaseModel, Field


class PortfolioSnapshot(BaseModel):
    """Point-in-time portfolio state."""

    balance: Decimal = Field(ge=0)
    equity: Decimal = Field(ge=0)

    realized_pnl: Decimal = Decimal(0)
    unrealized_pnl: Decimal = Decimal(0)

    open_positions: int = Field(default=0, ge=0)

    total_exposure: Decimal = Decimal(0)

    @property
    def net_pnl(self) -> Decimal:
        return self.realized_pnl + self.unrealized_pnl

    @property
    def available_equity(self) -> Decimal:
        return self.equity - self.total_exposure