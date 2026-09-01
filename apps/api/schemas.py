from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness response."""

    status: str


class RuntimeStatusResponse(BaseModel):
    """Current runtime operational status."""

    status: str
    started: bool
    running: bool
    execution_connected: bool
    symbols: list[str]
    interval_seconds: float = Field(gt=0)


class PortfolioResponse(BaseModel):
    """Current portfolio state."""

    balance: Decimal
    equity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    net_pnl: Decimal
    open_positions: int = Field(ge=0)
    total_exposure: Decimal
    available_equity: Decimal
    open_symbols: list[str]


class PositionResponse(BaseModel):
    """Current tracked position."""

    symbol: str
    side: str
    status: str
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    opened_at: datetime
    closed_at: datetime | None
    realized_pnl: Decimal
    unrealized_pnl: Decimal


class PositionsResponse(BaseModel):
    """Collection of tracked positions."""

    positions: list[PositionResponse]


class ErrorDetail(BaseModel):
    """Structured API error."""

    code: str
    message: str


class ErrorResponse(BaseModel):
    """Standard API error response."""

    error: ErrorDetail