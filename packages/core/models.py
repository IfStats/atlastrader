from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

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

    base_currency: str | None = None
    quote_currency: str | None = None

    exchange: str | None = None
    broker_symbol: str | None = None

    tick_size: Decimal = Field(gt=0)
    contract_size: Decimal = Field(gt=0)

    min_volume: Decimal = Field(gt=0)
    max_volume: Decimal | None = Field(default=None, gt=0)
    volume_step: Decimal = Field(gt=0)

    price_precision: int = Field(ge=0, le=10)
    volume_precision: int = Field(ge=0, le=10)

    market_status: MarketStatus = MarketStatus.UNKNOWN

    trading_timezone: str | None = None

    enabled: bool = False

    created_at: datetime
    updated_at: datetime


class Quote(BaseModel):
    symbol: str

    bid: Decimal = Field(gt=0)
    ask: Decimal = Field(gt=0)

    timestamp: datetime

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