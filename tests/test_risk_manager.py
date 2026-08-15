from decimal import Decimal

from packages.core.config import RiskSettings
from packages.core.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    SignalDirection,
    StrategyType,
    Timeframe,
)
from packages.core.models import MarketState, Order, Signal
from packages.risk.manager import DefaultRiskManager


def make_settings() -> RiskSettings:
    return RiskSettings(
        trading_enabled=True,
        max_risk_per_trade=Decimal("0.01"),
        max_daily_loss=Decimal("0.03"),
        max_open_positions=5,
        min_risk_reward_ratio=Decimal("1.5"),
        max_spread=Decimal("1.0"),
    )


def make_market_state() -> MarketState:
    from datetime import UTC, datetime

    return MarketState(
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        timestamp=datetime.now(UTC),
        price=Decimal(3350),
        trend_score=Decimal("0.8"),
        momentum_score=Decimal("0.7"),
        volatility_score=Decimal("0.5"),
        volatility=Decimal(5),
        spread=Decimal("0.20"),
        is_tradeable=True,
    )


def make_signal() -> Signal:
    from datetime import UTC, datetime

    return Signal(
        symbol="XAUUSD",
        direction=SignalDirection.LONG,
        strategy=StrategyType.MOMENTUM,
        score=85,
        timestamp=datetime.now(UTC),
        timeframe=Timeframe.M5,
        entry_price=Decimal(3350),
        stop_loss=Decimal(3345),
        take_profit=Decimal(3360),
        risk_reward_ratio=Decimal(2),
    )


def test_position_size_calculation() -> None:
    manager = DefaultRiskManager(make_settings())

    size = manager.calculate_position_size(
        account_balance=Decimal(10000),
        entry_price=Decimal(3350),
        stop_loss=Decimal(3345),
        contract_size=Decimal(100),
    )

    assert size == Decimal("0.2")


def test_can_trade_when_daily_loss_is_within_limit() -> None:
    manager = DefaultRiskManager(make_settings())

    assert manager.can_trade(Decimal("-0.01")) is True


def test_cannot_trade_when_daily_loss_limit_is_reached() -> None:
    manager = DefaultRiskManager(make_settings())

    assert manager.can_trade(Decimal(-300)) is False

def test_signal_is_approved_when_risk_controls_pass() -> None:
    manager = DefaultRiskManager(make_settings())

    assert manager.approve_signal(
        make_signal(),
        make_market_state(),
        [],
    ) is True


def test_signal_rejected_when_spread_is_too_high() -> None:
    manager = DefaultRiskManager(make_settings())
    market_state = make_market_state()
    market_state.spread = Decimal("2.0")

    assert manager.approve_signal(
        make_signal(),
        market_state,
        [],
    ) is False


def test_signal_rejected_when_risk_reward_is_too_low() -> None:
    manager = DefaultRiskManager(make_settings())
    signal = make_signal()
    signal.risk_reward_ratio = Decimal("1.0")

    assert manager.approve_signal(
        signal,
        make_market_state(),
        [],
    ) is False


def test_order_rejected_when_trading_disabled() -> None:
    manager = DefaultRiskManager(
        RiskSettings(trading_enabled=False)
    )

    from datetime import UTC, datetime

    order = Order(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.10"),
        status=OrderStatus.PENDING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    assert manager.validate_order(
        order,
        make_market_state(),
        [],
    ) is False