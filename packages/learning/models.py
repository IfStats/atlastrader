from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from packages.core.enums import (
    OrderSide,
    SignalDirection,
    StrategyType,
    Timeframe,
)


class LearningRecord(BaseModel):
    """Immutable supervised-learning record for one completed trade."""

    model_config = ConfigDict(
        frozen=True
    )

    decision_id: str
    trade_id: str

    atlas_order_id: str
    broker_order_id: str

    symbol: str
    strategy: StrategyType
    timeframe: Timeframe

    direction: SignalDirection
    side: OrderSide

    decision_timestamp: datetime
    opened_at: datetime
    closed_at: datetime

    signal_score: float = Field(
        ge=0,
        le=100,
    )
    confidence: float = Field(
        ge=0,
        le=1,
    )

    requested_quantity: Decimal = Field(
        gt=0
    )

    planned_entry_price: Decimal = Field(
        gt=0
    )
    executed_entry_price: Decimal = Field(
        gt=0
    )
    exit_price: Decimal = Field(
        gt=0
    )

    stop_loss: Decimal | None = Field(
        default=None,
        gt=0,
    )
    take_profit: Decimal | None = Field(
        default=None,
        gt=0,
    )
    risk_reward_ratio: Decimal | None = Field(
        default=None,
        gt=0,
    )

    market_state_price: Decimal = Field(
        gt=0
    )
    trend_score: float = Field(
        ge=-1,
        le=1,
    )
    momentum_score: float = Field(
        ge=-1,
        le=1,
    )
    volatility_score: float = Field(
        ge=0,
        le=1,
    )
    volatility: Decimal = Field(
        ge=0
    )
    spread: Decimal = Field(
        ge=0
    )

    market_status: str
    session: str | None = None
    is_tradeable: bool

    gross_pnl: Decimal
    commission: Decimal
    swap: Decimal
    net_pnl: Decimal

    exit_reason: str | None = None
    profitable: bool

    @model_validator(
        mode="after"
    )
    def validate_record(
        self,
    ) -> Self:
        if (
            self.direction
            is SignalDirection.FLAT
        ):
            raise ValueError(
                "Learning records require "
                "a directional decision"
            )

        if self.closed_at <= self.opened_at:
            raise ValueError(
                "closed_at must be later "
                "than opened_at"
            )

        expected_profitable = (
            self.net_pnl > Decimal(0)
        )

        if (
            self.profitable
            is not expected_profitable
        ):
            raise ValueError(
                "profitable must match "
                "the sign of net_pnl"
            )

        return self