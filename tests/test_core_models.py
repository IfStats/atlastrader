from datetime import UTC, datetime
from decimal import Decimal

from packages.core.enums import (
    AssetClass,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionStatus,
    SignalDirection,
    StrategyType,
    Timeframe,
)
from packages.core.models import (
    Candle,
    Instrument,
    MarketState,
    Order,
    Position,
    Quote,
    Signal,
)

NOW = datetime.now(UTC)


def test_instrument_creation() -> None:
    instrument = Instrument(
        symbol="XAUUSD",
        name="Gold / US Dollar",
        asset_class=AssetClass.METAL,
        quote_currency="USD",
        broker_symbol="XAUUSD",
        tick_size=Decimal("0.01"),
        contract_size=Decimal(100),
        min_volume=Decimal("0.01"),
        max_volume=Decimal(100),
        volume_step=Decimal("0.01"),
        price_precision=2,
        volume_precision=2,
        created_at=NOW,
        updated_at=NOW,
    )

    assert instrument.symbol == "XAUUSD"
    assert instrument.asset_class == AssetClass.METAL
    assert instrument.enabled is False


def test_quote_calculates_spread_and_mid_price() -> None:
    quote = Quote(
        symbol="XAUUSD",
        bid=Decimal("3348.21"),
        ask=Decimal("3348.42"),
        timestamp=NOW,
    )

    assert quote.spread == Decimal("0.21")
    assert quote.mid_price == Decimal("3348.315")


def test_candle_properties() -> None:
    candle = Candle(
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        timestamp=NOW,
        open=Decimal("3345.00"),
        high=Decimal("3350.00"),
        low=Decimal("3343.00"),
        close=Decimal("3349.00"),
        volume=Decimal(1000),
    )

    assert candle.range == Decimal("7.00")
    assert candle.body == Decimal("4.00")
    assert candle.bullish is True
    assert candle.bearish is False


def test_market_state() -> None:
    state = MarketState(
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        timestamp=NOW,
        price=Decimal("3349.00"),
        trend_score=0.82,
        momentum_score=0.71,
        volatility_score=0.64,
        volatility=Decimal("5.20"),
        spread=Decimal("0.21"),
        session="london_new_york",
        is_tradeable=True,
    )

    assert state.symbol == "XAUUSD"
    assert state.trend_score > 0
    assert state.is_tradeable is True


def test_signal_defaults_to_candidate() -> None:
    signal = Signal(
        symbol="XAUUSD",
        direction=SignalDirection.LONG,
        strategy=StrategyType.MOMENTUM,
        score=84,
        timestamp=NOW,
        timeframe=Timeframe.M5,
        entry_price=Decimal("3348.40"),
        stop_loss=Decimal("3344.20"),
        take_profit=Decimal("3356.80"),
        risk_reward_ratio=2.0,
        rationale=[
            "Bullish momentum",
            "Trend alignment",
            "Acceptable volatility",
        ],
    )

    assert signal.direction == SignalDirection.LONG
    assert signal.score == 84
    assert signal.status.value == "candidate"


def test_order_defaults() -> None:
    order = Order(
    id="order-001",
    symbol="XAUUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.10"),
        created_at=NOW,
        updated_at=NOW,
    )

    assert order.status == OrderStatus.PENDING
    assert order.quantity == Decimal("0.10")


def test_position_defaults() -> None:
    position = Position(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        quantity=Decimal("0.10"),
        entry_price=Decimal("3348.21"),
        current_price=Decimal("3350.21"),
        opened_at=NOW,
    )

    assert position.status == PositionStatus.OPEN
    assert position.unrealized_pnl == Decimal(0)




