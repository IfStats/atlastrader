from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.core.enums import (
    OrderSide,
    OrderStatus,
    SignalDirection,
    StrategyType,
    Timeframe,
)


class TradeDecision(BaseModel):
    """Immutable record of the reasoning and controls behind a trade decision."""

    model_config = ConfigDict(frozen=True)

    id: str
    symbol: str

    direction: SignalDirection
    strategy: StrategyType
    timeframe: Timeframe

    decision: SignalDirection
    status: str

    timestamp: datetime

    signal_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)

    entry_price: Decimal | None = Field(default=None, gt=0)
    stop_loss: Decimal | None = Field(default=None, gt=0)
    take_profit: Decimal | None = Field(default=None, gt=0)

    risk_reward_ratio: Decimal | None = Field(default=None, gt=0)
    requested_quantity: Decimal | None = Field(default=None, gt=0)

    risk_amount: Decimal | None = Field(default=None, ge=0)
    risk_percentage: Decimal | None = Field(default=None, ge=0, le=1)

    rationale: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)

    market_state: dict[str, object] = Field(default_factory=dict)

    order_id: str | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        if (
            self.decision == SignalDirection.FLAT
            and self.order_id is not None
):
                raise ValueError(
                    "FLAT decisions cannot have an order_id"
                )

        if (
             self.decision
             in (SignalDirection.LONG, SignalDirection.SHORT)
             and self.entry_price is None
):
                raise ValueError(
                    "Directional decisions require an entry_price"
                )

        return self


class TradeOutcome(BaseModel):
    """Record of the realized outcome of a completed trade."""

    trade_id: str
    symbol: str

    side: OrderSide
    order_status: OrderStatus

    entry_price: Decimal = Field(gt=0)
    exit_price: Decimal | None = Field(default=None, gt=0)

    quantity: Decimal = Field(gt=0)

    stop_loss: Decimal | None = Field(default=None, gt=0)
    take_profit: Decimal | None = Field(default=None, gt=0)

    gross_pnl: Decimal = Decimal(0)
    commission: Decimal = Decimal(0)
    swap: Decimal = Decimal(0)
    net_pnl: Decimal = Decimal(0)

    realized: bool = False

    opened_at: datetime
    closed_at: datetime | None = None

    exit_reason: str | None = None

    maximum_adverse_excursion: Decimal | None = Field(
        default=None,
        ge=0,
    )
    maximum_favorable_excursion: Decimal | None = Field(
        default=None,
        ge=0,
    )

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.realized:
            if self.exit_price is None:
                raise ValueError(
                    "Realized trades require an exit_price"
                )

            if self.closed_at is None:
                raise ValueError(
                    "Realized trades require closed_at"
                )

            if self.closed_at <= self.opened_at:
                raise ValueError(
                    "closed_at must be later than opened_at"
                )

        return self