from datetime import UTC, datetime
from decimal import Decimal

import pytest

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


def test_quote_allows_equal_bid_and_ask() -> None:
    quote = Quote(
        symbol="XAUUSD",
        bid=Decimal("3348.21"),
        ask=Decimal("3348.21"),
        timestamp=NOW,
    )

    assert quote.spread == Decimal(0)


def test_quote_rejects_ask_below_bid() -> None:
    with pytest.raises(
        ValueError,
        match="ask must be greater than or equal to bid",
    ):
        Quote(
            symbol="XAUUSD",
            bid=Decimal("3348.42"),
            ask=Decimal("3348.21"),
            timestamp=NOW,
        )


def test_quote_rejects_non_positive_bid() -> None:
    with pytest.raises(ValueError):
        Quote(
            symbol="XAUUSD",
            bid=Decimal(0),
            ask=Decimal("3348.21"),
            timestamp=NOW,
        )


def test_quote_rejects_non_positive_ask() -> None:
    with pytest.raises(ValueError):
        Quote(
            symbol="XAUUSD",
            bid=Decimal("3348.21"),
            ask=Decimal(-1),
            timestamp=NOW,
        )


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

def test_candle_allows_valid_ohlc() -> None:
    candle = Candle(
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        timestamp=NOW,
        open=Decimal("3345.00"),
        high=Decimal("3350.00"),
        low=Decimal("3343.00"),
        close=Decimal("3349.00"),
    )

    assert candle.high >= candle.open
    assert candle.high >= candle.close
    assert candle.low <= candle.open
    assert candle.low <= candle.close


def test_candle_rejects_high_below_open() -> None:
    with pytest.raises(
        ValueError,
        match="high must be greater than or equal to open",
    ):
        Candle(
            symbol="XAUUSD",
            timeframe=Timeframe.M5,
            timestamp=NOW,
            open=Decimal("3350.00"),
            high=Decimal("3349.00"),
            low=Decimal("3343.00"),
            close=Decimal("3347.00"),
        )


def test_candle_rejects_high_below_close() -> None:
    with pytest.raises(
        ValueError,
        match="high must be greater than or equal to close",
    ):
        Candle(
            symbol="XAUUSD",
            timeframe=Timeframe.M5,
            timestamp=NOW,
            open=Decimal("3345.00"),
            high=Decimal("3348.00"),
            low=Decimal("3343.00"),
            close=Decimal("3350.00"),
        )


def test_candle_rejects_low_above_open() -> None:
    with pytest.raises(
        ValueError,
        match="low must be less than or equal to open",
    ):
        Candle(
            symbol="XAUUSD",
            timeframe=Timeframe.M5,
            timestamp=NOW,
            open=Decimal("3345.00"),
            high=Decimal("3350.00"),
            low=Decimal("3346.00"),
            close=Decimal("3348.00"),
        )

def test_candle_rejects_low_above_close() -> None:
    with pytest.raises(
        ValueError,
        match="low must be less than or equal to close",
    ):
        Candle(
            symbol="XAUUSD",
            timeframe=Timeframe.M5,
            timestamp=NOW,
            open=Decimal("3350.00"),
            high=Decimal("3352.00"),
            low=Decimal("3349.00"),
            close=Decimal("3348.00"),
        )

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

def test_instrument_allows_missing_max_volume() -> None:
    instrument = Instrument(
        symbol="EURUSD",
        name="Euro / US Dollar",
        asset_class=AssetClass.FOREX,
        base_currency="EUR",
        quote_currency="USD",
        broker_symbol="EURUSD",
        tick_size=Decimal("0.00001"),
        contract_size=Decimal(100000),
        min_volume=Decimal("0.01"),
        volume_step=Decimal("0.01"),
        price_precision=5,
        volume_precision=2,
        created_at=NOW,
        updated_at=NOW,
    )

    assert instrument.max_volume is None


def test_instrument_rejects_non_positive_tick_size() -> None:
    with pytest.raises(ValueError):
        Instrument(
            symbol="XAUUSD",
            name="Gold / US Dollar",
            asset_class=AssetClass.METAL,
            quote_currency="USD",
            tick_size=Decimal(0),
            contract_size=Decimal(100),
            min_volume=Decimal("0.01"),
            volume_step=Decimal("0.01"),
            price_precision=2,
            volume_precision=2,
            created_at=NOW,
            updated_at=NOW,
        )


def test_instrument_rejects_non_positive_contract_size() -> None:
    with pytest.raises(ValueError):
        Instrument(
            symbol="XAUUSD",
            name="Gold / US Dollar",
            asset_class=AssetClass.METAL,
            quote_currency="USD",
            tick_size=Decimal("0.01"),
            contract_size=Decimal(0),
            min_volume=Decimal("0.01"),
            volume_step=Decimal("0.01"),
            price_precision=2,
            volume_precision=2,
            created_at=NOW,
            updated_at=NOW,
        )


def test_instrument_rejects_non_positive_min_volume() -> None:
    with pytest.raises(ValueError):
        Instrument(
            symbol="XAUUSD",
            name="Gold / US Dollar",
            asset_class=AssetClass.METAL,
            quote_currency="USD",
            tick_size=Decimal("0.01"),
            contract_size=Decimal(100),
            min_volume=Decimal(0),
            volume_step=Decimal("0.01"),
            price_precision=2,
            volume_precision=2,
            created_at=NOW,
            updated_at=NOW,
        )


def test_instrument_rejects_non_positive_volume_step() -> None:
    with pytest.raises(ValueError):
        Instrument(
            symbol="XAUUSD",
            name="Gold / US Dollar",
            asset_class=AssetClass.METAL,
            quote_currency="USD",
            tick_size=Decimal("0.01"),
            contract_size=Decimal(100),
            min_volume=Decimal("0.01"),
            volume_step=Decimal(0),
            price_precision=2,
            volume_precision=2,
            created_at=NOW,
            updated_at=NOW,
        )

def test_instrument_rejects_max_volume_below_min_volume() -> None:
    with pytest.raises(
        ValueError,
        match="max_volume must be greater than or equal to min_volume",
    ):
        Instrument(
            symbol="XAUUSD",
            name="Gold / US Dollar",
            asset_class=AssetClass.METAL,
            quote_currency="USD",
            tick_size=Decimal("0.01"),
            contract_size=Decimal(100),
            min_volume=Decimal("1.00"),
            max_volume=Decimal("0.50"),
            volume_step=Decimal("0.01"),
            price_precision=2,
            volume_precision=2,
            created_at=NOW,
            updated_at=NOW,
        )


def test_instrument_rejects_min_volume_not_aligned_to_step() -> None:
    with pytest.raises(
        ValueError,
        match="min_volume must be aligned with volume_step",
    ):
        Instrument(
            symbol="XAUUSD",
            name="Gold / US Dollar",
            asset_class=AssetClass.METAL,
            quote_currency="USD",
            tick_size=Decimal("0.01"),
            contract_size=Decimal(100),
            min_volume=Decimal("0.015"),
            max_volume=Decimal(100),
            volume_step=Decimal("0.01"),
            price_precision=2,
            volume_precision=3,
            created_at=NOW,
            updated_at=NOW,
        )


def test_instrument_rejects_max_volume_not_aligned_to_step() -> None:
    with pytest.raises(
        ValueError,
        match="max_volume must be aligned with volume_step",
    ):
        Instrument(
            symbol="XAUUSD",
            name="Gold / US Dollar",
            asset_class=AssetClass.METAL,
            quote_currency="USD",
            tick_size=Decimal("0.01"),
            contract_size=Decimal(100),
            min_volume=Decimal("0.01"),
            max_volume=Decimal("100.005"),
            volume_step=Decimal("0.01"),
            price_precision=2,
            volume_precision=3,
            created_at=NOW,
            updated_at=NOW,
        )