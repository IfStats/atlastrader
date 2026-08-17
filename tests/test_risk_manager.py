from datetime import UTC, datetime
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
        max_portfolio_exposure=Decimal("0.50"),
        min_risk_reward_ratio=Decimal("1.5"),
        max_spread=Decimal("5.0"),
    )


def make_market_state() -> MarketState:
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


def test_can_trade_when_daily_loss_is_within_limit() -> None:
    manager = DefaultRiskManager(make_settings())

    assert manager.can_trade(Decimal(-100)) is True


def test_can_trade_rejected_when_daily_loss_exceeds_limit() -> None:
    manager = DefaultRiskManager(make_settings())

    assert manager.can_trade(Decimal(-300)) is False


def test_signal_is_approved_when_risk_controls_pass() -> None:
    manager = DefaultRiskManager(make_settings())
    signal = make_signal()
    market_state = make_market_state()

    assert manager.approve_signal(signal, market_state) is True


def test_signal_rejected_when_market_is_not_tradeable() -> None:
    manager = DefaultRiskManager(make_settings())
    signal = make_signal()

    market_state = make_market_state()
    market_state = market_state.model_copy(
        update={"is_tradeable": False}
    )

    assert manager.approve_signal(signal, market_state) is False


def test_position_size_is_calculated_from_risk() -> None:
    manager = DefaultRiskManager(make_settings())

    size = manager.calculate_position_size(
        account_balance=Decimal(10000),
        entry_price=Decimal(3350),
        stop_loss=Decimal(3345),
        contract_size=Decimal(100),
    )

    assert size > Decimal(0)


def test_order_rejected_when_trading_disabled() -> None:
    manager = DefaultRiskManager(
        RiskSettings(trading_enabled=False)
    )

    order = Order(
        id="order-002",
        symbol="XAUUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.10"),
        status=OrderStatus.PENDING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    assert manager.validate_order(order) is False


def test_order_accepted_when_trading_enabled() -> None:
    manager = DefaultRiskManager(make_settings())

    order = Order(
        id="order-003",
        symbol="XAUUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.10"),
        status=OrderStatus.PENDING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    assert manager.validate_order(order) is True

def test_signal_rejected_when_portfolio_exposure_exceeds_limit() -> None:
    manager = DefaultRiskManager(make_settings())

    signal = make_signal()
    market_state = make_market_state()

    assert (
        manager.approve_signal(
            signal,
            market_state,
            open_positions=1,
            current_exposure=Decimal(5001),
        )
        is False
    )


def test_signal_approved_when_portfolio_exposure_is_within_limit() -> None:
    manager = DefaultRiskManager(make_settings())

    signal = make_signal()
    market_state = make_market_state()

    assert (
        manager.approve_signal(
            signal,
            market_state,
            open_positions=1,
            current_exposure=Decimal(4000),
        )
        is True
    )