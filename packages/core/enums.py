from enum import StrEnum


class AssetClass(StrEnum):
    FOREX = "forex"
    METAL = "metal"
    INDEX = "index"
    COMMODITY = "commodity"
    CRYPTO = "crypto"


class MarketStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    HALTED = "halted"
    UNKNOWN = "unknown"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class OrderStatus(StrEnum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PositionStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class SignalDirection(StrEnum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class SignalStatus(StrEnum):
    CANDIDATE = "candidate"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class StrategyType(StrEnum):
    SCALPING = "scalping"
    MOMENTUM = "momentum"
    TREND_FOLLOWING = "trend_following"
    BREAKOUT = "breakout"
    PULLBACK = "pullback"
    MEAN_REVERSION = "mean_reversion"


class Timeframe(StrEnum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"