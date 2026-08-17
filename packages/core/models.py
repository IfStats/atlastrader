from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from packages.core.enums import (
    AssetClass,
    MarketStatus,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionStatus,
    SignalDirection,
    SignalStatus,
    StrategyType,
    Timeframe,
)


class Instrument(BaseModel):
    symbol: str
    name: str
    asset_class: AssetClass
    quote_currency: str = "USD"
    broker_symbol: str = ""
    tick_size: Decimal = Field(gt=0)
    contract_size: Decimal = Field(gt=0)
    min_volume: Decimal = Field(gt=0)
    max_volume: Decimal | None = None
    volume_step: Decimal
    price_precision: int
    volume_precision: int
    enabled: bool = False
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_volume_constraints(self) -> "Instrument":
        if (
            self.max_volume is not None
            and self.max_volume < self.min_volume
        ):
            raise ValueError(
                "max_volume must be greater than or equal to min_volume"
            )

        if self.volume_step <= 0:
            raise ValueError("volume_step must be greater than zero")

        if self.min_volume % self.volume_step != 0:
            raise ValueError(
                "min_volume must be aligned with volume_step"
            )

        if (
            self.max_volume is not None
            and self.max_volume % self.volume_step != 0
        ):
            raise ValueError(
                "max_volume must be aligned with volume_step"
            )

        return self

class Quote(BaseModel):
    symbol: str

    bid: Decimal = Field(gt=0)
    ask: Decimal = Field(gt=0)

    timestamp: datetime

    @model_validator(mode="after")
    def validate_bid_ask(self) -> "Quote":
        if self.ask < self.bid:
            raise ValueError(
                "ask must be greater than or equal to bid"
            )

        return self

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid

    @property
    def mid_price(self) -> Decimal:
        return (self.bid + self.ask) / Decimal(2)


class Candle(BaseModel):
    symbol: str
    timeframe: Timeframe

    timestamp: datetime

    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)

    volume: Decimal = Field(default=Decimal(0), ge=0)

    @model_validator(mode="after")
    def validate_ohlc(self) -> "Candle":
        """Validate the internal consistency of OHLC prices."""

        if self.high < self.open:
            raise ValueError(
                "high must be greater than or equal to open"
            )

        if self.high < self.close:
            raise ValueError(
                "high must be greater than or equal to close"
            )

        if self.low > self.open:
            raise ValueError(
                "low must be less than or equal to open"
            )

        if self.low > self.close:
            raise ValueError(
                "low must be less than or equal to close"
            )

        return self

    @property
    def range(self) -> Decimal:
        return self.high - self.low

    @property
    def body(self) -> Decimal:
        return abs(self.close - self.open)

    @property
    def bullish(self) -> bool:
        return self.close > self.open

    @property
    def bearish(self) -> bool:
        return self.close < self.open



class MarketState(BaseModel):
    symbol: str
    timestamp: datetime

    timeframe: Timeframe

    price: Decimal = Field(gt=0)

    trend_score: float = Field(ge=-1, le=1)
    momentum_score: float = Field(ge=-1, le=1)
    volatility_score: float = Field(ge=0, le=1)

    volatility: Decimal = Field(ge=0)

    spread: Decimal = Field(ge=0)

    market_status: MarketStatus = MarketStatus.UNKNOWN

    session: str | None = None

    is_tradeable: bool = False


class Signal(BaseModel):
    symbol: str
    direction: SignalDirection

    strategy: StrategyType

    status: SignalStatus = SignalStatus.CANDIDATE

    score: float = Field(ge=0, le=100)

    timestamp: datetime

    timeframe: Timeframe

    entry_price: Decimal | None = Field(default=None, gt=0)
    stop_loss: Decimal | None = Field(default=None, gt=0)
    take_profit: Decimal | None = Field(default=None, gt=0)

    risk_reward_ratio: float | None = Field(default=None, gt=0)

    rationale: list[str] = Field(default_factory=list)


class Order(BaseModel):
    """An instruction that can be sent to an execution venue."""

    id: str
    symbol: str

    side: OrderSide
    order_type: OrderType
    status: OrderStatus = OrderStatus.PENDING

    quantity: Decimal = Field(gt=0)

    price: Decimal | None = Field(default=None, gt=0)
    stop_loss: Decimal | None = Field(default=None, gt=0)
    take_profit: Decimal | None = Field(default=None, gt=0)

    signal_id: str | None = None

    created_at: datetime
    updated_at: datetime

class Position(BaseModel):
    """An open or closed trading position."""

    symbol: str

    side: OrderSide
    status: PositionStatus = PositionStatus.OPEN

    quantity: Decimal = Field(gt=0)

    entry_price: Decimal = Field(gt=0)
    current_price: Decimal = Field(gt=0)

    stop_loss: Decimal | None = Field(default=None, gt=0)
    take_profit: Decimal | None = Field(default=None, gt=0)

    opened_at: datetime
    closed_at: datetime | None = None

    realized_pnl: Decimal = Decimal(0)
    unrealized_pnl: Decimal = Decimal(0)