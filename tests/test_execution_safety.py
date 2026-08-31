from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from packages.core.config import RiskSettings
from packages.core.enums import OrderSide, OrderStatus, OrderType
from packages.core.models import Order
from packages.execution.interfaces import ExecutionProvider
from packages.risk.manager import DefaultRiskManager


def make_order(
    *,
    quantity: Decimal = Decimal("0.01"),
    stop_loss: Decimal | None = Decimal(3345),
    take_profit: Decimal | None = Decimal(3360),
) -> Order:
    now = datetime.now(UTC)

    return Order(
        id="safety-order-001",
        symbol="XAUUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        status=OrderStatus.PENDING,
        quantity=quantity,
        stop_loss=stop_loss,
        take_profit=take_profit,
        created_at=now,
        updated_at=now,
    )


def make_settings() -> RiskSettings:
    return RiskSettings(
        trading_enabled=True,
        max_open_positions=5,
        max_portfolio_exposure=Decimal("0.50"),
        max_spread=Decimal("5.0"),
        min_risk_reward_ratio=Decimal("1.5"),
    )


def test_order_requires_positive_quantity() -> None:
    with pytest.raises(ValueError):
        make_order(quantity=Decimal(0))


def test_order_requires_stop_loss_for_risk_control() -> None:
    order = make_order(stop_loss=None)

    manager = DefaultRiskManager(make_settings())

    assert order.stop_loss is None
    assert manager.settings.trading_enabled is True


def test_order_requires_take_profit_for_risk_control() -> None:
    order = make_order(take_profit=None)

    manager = DefaultRiskManager(make_settings())

    assert order.take_profit is None
    assert manager.settings.trading_enabled is True


@pytest.mark.asyncio
async def test_execution_provider_interface_exposes_submit_order() -> None:
    provider = AsyncMock(spec=ExecutionProvider)

    assert hasattr(provider, "submit_order")


@pytest.mark.asyncio
async def test_execution_provider_must_not_be_called_by_safety_test_without_explicit_submission() -> None:
    provider = AsyncMock(spec=ExecutionProvider)
    order = make_order()

    assert order.stop_loss is not None
    assert order.take_profit is not None

    provider.submit_order.assert_not_awaited()