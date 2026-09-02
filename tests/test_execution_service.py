from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from packages.core.enums import (
    AssetClass,
    MarketStatus,
    OrderSide,
    OrderStatus,
    OrderType,
    Timeframe,
)
from packages.core.models import Instrument, MarketState, Order
from packages.execution.interfaces import ExecutionProvider
from packages.execution.safety import (
    ExecutionSafetyDecision,
    ExecutionSafetyGate,
)
from packages.execution.service import ExecutionService
from packages.risk.interfaces import RiskManager


def make_instrument() -> Instrument:
    """Create a valid test instrument."""
    now = datetime.now(UTC)

    return Instrument(
        symbol="XAUUSD",
        name="XAUUSD",
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
        enabled=True,
        created_at=now,
        updated_at=now,
    )


def make_market_state() -> MarketState:
    """Create a valid tradeable market state."""
    return MarketState(
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        timestamp=datetime.now(UTC),
        price=Decimal(3350),
        trend_score=Decimal("0.90"),
        momentum_score=Decimal("0.90"),
        volatility_score=Decimal("0.50"),
        volatility=Decimal(5),
        spread=Decimal("0.20"),
        status=MarketStatus.OPEN,
        is_tradeable=True,
    )


def make_order(
    *,
    status: OrderStatus = OrderStatus.PENDING,
) -> Order:
    """Create a valid test order."""
    now = datetime.now(UTC)

    return Order(
        id=str(uuid4()),
        symbol="XAUUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        stop_loss=Decimal(3345),
        take_profit=Decimal(3360),
        status=status,
        created_at=now,
        updated_at=now,
    )


def make_provider() -> AsyncMock:
    """Create an execution provider test double."""
    provider = AsyncMock(spec=ExecutionProvider)

    provider.is_connected.return_value = True
    provider.get_instrument.return_value = make_instrument()
    provider.get_position.return_value = None
    provider.submit_order.return_value = make_order(
        status=OrderStatus.FILLED,
    )

    return provider


def make_risk_manager(*, approved: bool = True) -> MagicMock:
    """Create a risk manager test double."""
    risk_manager = MagicMock(spec=RiskManager)
    risk_manager.validate_order.return_value = approved
    return risk_manager


def make_safety_gate(
    *,
    authorized: bool = True,
) -> AsyncMock:
    """Create an execution safety gate test double."""
    safety_gate = AsyncMock(spec=ExecutionSafetyGate)

    if authorized:
        safety_gate.authorize.return_value = (
            ExecutionSafetyDecision.allow()
        )
    else:
        safety_gate.authorize.return_value = (
            ExecutionSafetyDecision.block(
                "Execution terminal trading is disabled",
            )
        )

    return safety_gate


@pytest.mark.asyncio
async def test_execution_service_submits_when_risk_and_safety_approve() -> None:
    """An order reaches the provider only after both gates approve."""
    provider = make_provider()
    risk_manager = make_risk_manager(approved=True)
    safety_gate = make_safety_gate(authorized=True)

    service = ExecutionService(
        provider=provider,
        risk_manager=risk_manager,
        safety_gate=safety_gate,
    )

    order = make_order()
    market_state = make_market_state()

    result = await service.submit_order(
        order,
        market_state=market_state,
    )

    risk_manager.validate_order.assert_called_once()
    safety_gate.authorize.assert_awaited_once_with(
        order,
        market_state=market_state,
    )
    provider.submit_order.assert_awaited_once_with(order)

    assert result.status == OrderStatus.FILLED


@pytest.mark.asyncio
async def test_execution_service_blocks_provider_when_safety_rejects() -> None:
    """A safety block must prevent provider submission."""
    provider = make_provider()
    risk_manager = make_risk_manager(approved=True)
    safety_gate = make_safety_gate(authorized=False)

    service = ExecutionService(
        provider=provider,
        risk_manager=risk_manager,
        safety_gate=safety_gate,
    )

    order = make_order()
    market_state = make_market_state()

    result = await service.submit_order(
        order,
        market_state=market_state,
    )

    risk_manager.validate_order.assert_called_once()
    safety_gate.authorize.assert_awaited_once_with(
        order,
        market_state=market_state,
    )
    provider.submit_order.assert_not_awaited()

    assert result.status == OrderStatus.REJECTED


@pytest.mark.asyncio
async def test_execution_service_does_not_call_safety_when_risk_rejects() -> None:
    """Risk rejection must stop execution before safety authorization."""
    provider = make_provider()
    risk_manager = make_risk_manager(approved=False)
    safety_gate = make_safety_gate(authorized=True)

    service = ExecutionService(
        provider=provider,
        risk_manager=risk_manager,
        safety_gate=safety_gate,
    )

    order = make_order()
    market_state = make_market_state()

    result = await service.submit_order(
        order,
        market_state=market_state,
    )

    risk_manager.validate_order.assert_called_once()
    safety_gate.authorize.assert_not_awaited()
    provider.submit_order.assert_not_awaited()

    assert result.status == OrderStatus.REJECTED


@pytest.mark.asyncio
async def test_execution_service_passes_market_state_to_safety_gate() -> None:
    """The market state used for risk must also reach the safety gate."""
    provider = make_provider()
    risk_manager = make_risk_manager(approved=True)
    safety_gate = make_safety_gate(authorized=True)

    service = ExecutionService(
        provider=provider,
        risk_manager=risk_manager,
        safety_gate=safety_gate,
    )

    order = make_order()
    market_state = make_market_state()

    await service.submit_order(
        order,
        market_state=market_state,
    )

    safety_gate.authorize.assert_awaited_once_with(
        order,
        market_state=market_state,
    )