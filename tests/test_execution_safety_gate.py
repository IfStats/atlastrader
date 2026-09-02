from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.enums import (
    AssetClass,
    MarketStatus,
    OrderSide,
    OrderStatus,
    OrderType,
    Timeframe,
)
from packages.core.models import Instrument, MarketState, Order, Position
from packages.execution.interfaces import ExecutionProvider
from packages.execution.safety import (
    DefaultExecutionSafetyGate,
    ExecutionSafetyDecision,
)


def make_instrument(
    *,
    symbol: str = "XAUUSD",
    enabled: bool = True,
) -> Instrument:
    now = datetime.now(UTC)

    return Instrument(
        symbol=symbol,
        name=symbol,
        asset_class=AssetClass.METAL,
        quote_currency="USD",
        broker_symbol=symbol,
        tick_size=Decimal("0.01"),
        contract_size=Decimal(100),
        min_volume=Decimal("0.01"),
        max_volume=Decimal(100),
        volume_step=Decimal("0.01"),
        price_precision=2,
        volume_precision=2,
        enabled=enabled,
        created_at=now,
        updated_at=now,
    )


def make_market_state(
    *,
    tradeable: bool = True,
) -> MarketState:
    return MarketState(
        symbol="XAUUSD",
        timestamp=datetime.now(UTC),
        timeframe=Timeframe.M5,
        price=Decimal(3350),
        trend_score=Decimal("0.90"),
        momentum_score=Decimal("0.90"),
        volatility_score=Decimal("0.50"),
        volatility=Decimal(5),
        spread=Decimal("0.20"),
        market_status=MarketStatus.OPEN,
        is_tradeable=tradeable,
    )


def make_order(
    *,
    quantity: Decimal = Decimal("0.01"),
) -> Order:
    now = datetime.now(UTC)

    return Order(
        id="safety-gate-order-001",
        symbol="XAUUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        status=OrderStatus.PENDING,
        quantity=quantity,
        stop_loss=Decimal(3345),
        take_profit=Decimal(3360),
        created_at=now,
        updated_at=now,
    )


def make_provider() -> AsyncMock:
    provider = AsyncMock(spec=ExecutionProvider)

    provider.is_connected.return_value = True
    provider.get_instrument.return_value = make_instrument()
    provider.get_position.return_value = None

    return provider


def add_venue_authorization_methods(
    provider: AsyncMock,
    *,
    terminal_trade_allowed: bool = True,
    tradeapi_disabled: bool = False,
    account_trade_allowed: bool = True,
    account_trade_expert: bool = True,
) -> None:
    terminal = MagicMock()
    terminal.connected = True
    terminal.trade_allowed = terminal_trade_allowed
    terminal.tradeapi_disabled = tradeapi_disabled

    account = MagicMock()
    account.trade_allowed = account_trade_allowed
    account.trade_expert = account_trade_expert

    provider.get_terminal_snapshot = AsyncMock(
        return_value=terminal,
    )
    provider.get_account_snapshot = AsyncMock(
        return_value=account,
    )


@pytest.mark.asyncio
async def test_gate_authorizes_valid_order() -> None:
    provider = make_provider()
    gate = DefaultExecutionSafetyGate(provider=provider)

    decision = await gate.authorize(
        make_order(),
        market_state=make_market_state(),
    )

    assert decision == ExecutionSafetyDecision.allow()
    assert decision.authorized is True
    assert decision.reasons == ()


@pytest.mark.asyncio
async def test_gate_blocks_when_provider_is_not_connected() -> None:
    provider = make_provider()
    provider.is_connected.return_value = False

    gate = DefaultExecutionSafetyGate(provider=provider)

    decision = await gate.authorize(
        make_order(),
        market_state=make_market_state(),
    )

    assert decision.authorized is False
    assert "Execution provider is not connected" in decision.reasons


@pytest.mark.asyncio
async def test_gate_blocks_non_tradeable_market() -> None:
    provider = make_provider()
    gate = DefaultExecutionSafetyGate(provider=provider)

    decision = await gate.authorize(
        make_order(),
        market_state=make_market_state(tradeable=False),
    )

    assert decision.authorized is False
    assert "Market is not tradeable: XAUUSD" in decision.reasons


@pytest.mark.asyncio
async def test_gate_blocks_invalid_market_price() -> None:
    provider = make_provider()
    gate = DefaultExecutionSafetyGate(provider=provider)

    market_state = make_market_state().model_copy(
        update={
            "price": Decimal(0),
        }
    )

    decision = await gate.authorize(
        make_order(),
        market_state=market_state,
    )

    assert decision.authorized is False
    assert "Invalid market price: XAUUSD" in decision.reasons


@pytest.mark.asyncio
async def test_gate_blocks_existing_position() -> None:
    provider = make_provider()
    provider.get_position.return_value = MagicMock(spec=Position)

    gate = DefaultExecutionSafetyGate(provider=provider)

    decision = await gate.authorize(
        make_order(),
        market_state=make_market_state(),
    )

    assert decision.authorized is False
    assert (
        "Existing position blocks new order: XAUUSD"
        in decision.reasons
    )


@pytest.mark.asyncio
async def test_gate_blocks_quantity_below_minimum() -> None:
    provider = make_provider()
    gate = DefaultExecutionSafetyGate(provider=provider)

    decision = await gate.authorize(
        make_order(quantity=Decimal("0.001")),
        market_state=make_market_state(),
    )

    assert decision.authorized is False
    assert (
        "Order quantity 0.001 is below minimum volume 0.01"
        in decision.reasons
    )


@pytest.mark.asyncio
async def test_gate_blocks_quantity_above_maximum() -> None:
    provider = make_provider()
    gate = DefaultExecutionSafetyGate(provider=provider)

    decision = await gate.authorize(
        make_order(quantity=Decimal(101)),
        market_state=make_market_state(),
    )

    assert decision.authorized is False
    assert (
        "Order quantity 101 exceeds maximum volume 100"
        in decision.reasons
    )


@pytest.mark.asyncio
async def test_gate_blocks_invalid_volume_step() -> None:
    provider = make_provider()
    gate = DefaultExecutionSafetyGate(provider=provider)

    decision = await gate.authorize(
        make_order(quantity=Decimal("0.015")),
        market_state=make_market_state(),
    )

    assert decision.authorized is False
    assert any(
        "must be aligned with volume step 0.01" in reason
        for reason in decision.reasons
    )


@pytest.mark.asyncio
async def test_gate_blocks_terminal_trading_disabled() -> None:
    provider = make_provider()

    add_venue_authorization_methods(
        provider,
        terminal_trade_allowed=False,
    )

    gate = DefaultExecutionSafetyGate(provider=provider)

    decision = await gate.authorize(
        make_order(),
        market_state=make_market_state(),
    )

    assert decision.authorized is False
    assert "Execution terminal trading is disabled" in decision.reasons


@pytest.mark.asyncio
async def test_gate_blocks_account_expert_trading_disabled() -> None:
    provider = make_provider()

    add_venue_authorization_methods(
        provider,
        account_trade_expert=False,
    )

    gate = DefaultExecutionSafetyGate(provider=provider)

    decision = await gate.authorize(
        make_order(),
        market_state=make_market_state(),
    )

    assert decision.authorized is False
    assert (
        "Execution account expert trading is not allowed"
        in decision.reasons
    )