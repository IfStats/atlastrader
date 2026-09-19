import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.engine import main as app
from packages.core.enums import PositionStatus
from packages.core.models import Position
from packages.execution.safety import ExecutionSafetyDecision


@pytest.mark.asyncio
async def test_main_creates_and_starts_runtime() -> None:
    runtime = AsyncMock()
    runtime_settings = app.RuntimeSettings(
        symbols="XAUUSD",
        initial_balance=Decimal(10000),
    )

    with (
        patch.object(
            app,
            "RuntimeSettings",
            return_value=runtime_settings,
        ),
        patch.object(
            app,
            "RiskSettings",
            return_value=app.RiskSettings(
                trading_enabled=False,
            ),
        ),
        patch.object(
            app,
            "MT5Settings",
            return_value=app.MT5Settings(),
        ),
        patch.object(
            app,
            "create_runtime",
            return_value=runtime,
        ),
        patch.object(
            asyncio.Event,
            "wait",
            new=AsyncMock(
                side_effect=asyncio.CancelledError,
            ),
        ),
    ):
        await app.main()

    runtime.start.assert_awaited_once()
    runtime.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_main_rejects_empty_symbol_configuration() -> None:
    runtime_settings = app.RuntimeSettings(
        symbols="",
    )

    with patch.object(
        app,
        "RuntimeSettings",
        return_value=runtime_settings,
    ), pytest.raises(
        ValueError,
        match="No trading symbols configured",
    ):
        await app.main()


@pytest.mark.asyncio
async def test_main_stops_runtime_when_start_fails() -> None:
    runtime = AsyncMock()
    runtime.start.side_effect = RuntimeError("Startup failed")

    runtime_settings = app.RuntimeSettings(
        symbols="XAUUSD",
    )

    with (
        patch.object(
            app,
            "RuntimeSettings",
            return_value=runtime_settings,
        ),
        patch.object(
            app,
            "RiskSettings",
            return_value=app.RiskSettings(
                trading_enabled=False,
            ),
        ),
        patch.object(
            app,
            "MT5Settings",
            return_value=app.MT5Settings(),
        ),
        patch.object(
            app,
            "create_runtime",
            return_value=runtime,
        ),pytest.raises(
        RuntimeError,
        match="Startup failed",
    )
    ):
        await app.main()

    runtime.start.assert_awaited_once()
    runtime.stop.assert_awaited_once()

def test_build_demo_order_preserves_contract_size() -> None:
    order = app.build_demo_order(
        side=app.OrderSide.BUY,
        price=Decimal(3350),
        contract_size=Decimal(100),
    )

    assert order.contract_size == Decimal(100)

def test_demo_portfolio_snapshot_includes_existing_position_exposure() -> None:
    position = Position(
        symbol="AUDUSD",
        side=app.OrderSide.BUY,
        status=PositionStatus.OPEN,
        quantity=Decimal("0.01"),
        contract_size=Decimal(100000),
        entry_price=Decimal("0.71043"),
        current_price=Decimal("0.71043"),
        opened_at=app.datetime.now(app.UTC),
    )

    snapshot = app.build_demo_portfolio_snapshot(
        balance=Decimal("1864.43"),
        equity=Decimal("1871.29"),
        positions=[position],
    )

    assert snapshot.open_positions == 1
    assert snapshot.total_exposure == Decimal("710.43")
    assert snapshot.equity == Decimal("1871.29")    

@pytest.mark.asyncio
async def test_main_routes_demo_order_dry_run() -> None:
    run_demo_order = AsyncMock(return_value=0)

    with patch.object(
        app,
        "run_demo_order",
        run_demo_order,
    ):
        result = await app.main(
            [
                "--demo-order",
                "--side",
                "BUY",
                "--dry-run",
            ]
        )

    assert result == 0
    run_demo_order.assert_awaited_once_with(
        symbol="XAUUSD",
        side=app.OrderSide.BUY,
        dry_run=True,
    )

@pytest.mark.asyncio
async def test_demo_order_dry_run_checks_safety_without_submitting() -> None:
    execution_provider = AsyncMock()
    market_data_provider = AsyncMock()

    execution_provider.get_account_snapshot.return_value = SimpleNamespace(
        balance=Decimal(10000),
        equity=Decimal(10000),
    )
    execution_provider.get_position.return_value = None
    execution_provider.get_positions.return_value = []
    execution_provider.get_instrument.return_value = SimpleNamespace(
        contract_size=Decimal(100),
        tick_size=Decimal("0.01"),
    )

    market_data_provider.get_quote.return_value = SimpleNamespace(
        ask=Decimal(3350),
        bid=Decimal("3349.80"),
        spread=Decimal("0.20"),
        timestamp=app.datetime.now(app.UTC),
    )

    preflight = AsyncMock()
    preflight.run.return_value = SimpleNamespace(
        ready=True,
        blockers=[],
        quote_status={"XAUUSD": True},
    )

    risk_manager = MagicMock()
    risk_manager.validate_order.return_value = True

    execution_service = MagicMock()
    execution_service.safety_gate.authorize = AsyncMock(
        return_value=ExecutionSafetyDecision.allow()
    )
    execution_service.submit_order = AsyncMock()

    with (
        patch.object(
            app,
            "RiskSettings",
            return_value=app.RiskSettings(
                trading_enabled=False,
            ),
        ),
        patch.object(
            app,
            "create_mt5_providers",
            new=AsyncMock(
                return_value=(
                    execution_provider,
                    market_data_provider,
                )
            ),
        ),
        patch.object(
            app,
            "MT5Preflight",
            return_value=preflight,
        ),
        patch.object(
            app,
            "DefaultRiskManager",
            return_value=risk_manager,
        ),
        patch.object(
            app,
            "ExecutionService",
            return_value=execution_service,
        ),
    ):
        result = await app.run_demo_order(
            side=app.OrderSide.BUY,
            dry_run=True,
        )

    assert result == 0

    execution_provider.connect.assert_awaited_once()
    risk_manager.validate_order.assert_called_once()
    execution_service.safety_gate.authorize.assert_awaited_once()

    execution_service.submit_order.assert_not_awaited()
    execution_provider.submit_order.assert_not_awaited()

@pytest.mark.asyncio
async def test_main_routes_demo_order_symbol() -> None:
    run_demo_order = AsyncMock(return_value=0)

    with patch.object(
        app,
        "run_demo_order",
        run_demo_order,
    ):
        result = await app.main(
            [
                "--demo-order",
                "--symbol",
                "AUDUSD",
                "--side",
                "BUY",
                "--dry-run",
            ]
        )

    assert result == 0
    run_demo_order.assert_awaited_once_with(
        symbol="AUDUSD",
        side=app.OrderSide.BUY,
        dry_run=True,
    )

def test_build_demo_order_uses_instrument_tick_size() -> None:
    order = app.build_demo_order(
        symbol="EURUSD",
        side=app.OrderSide.BUY,
        price=Decimal("1.08500"),
        contract_size=Decimal(100000),
        tick_size=Decimal("0.00001"),
    )

    assert order.symbol == "EURUSD"
    assert order.stop_loss == Decimal("1.08000")
    assert order.take_profit == Decimal("1.09500")

@pytest.mark.asyncio
async def test_demo_order_fails_closed_when_quote_not_live() -> None:
    execution_provider = AsyncMock()
    market_data_provider = AsyncMock()

    execution_provider.get_position.return_value = None

    market_data_provider.get_quote.return_value = SimpleNamespace(
        ask=Decimal("3350.20"),
        bid=Decimal("3350.00"),
        spread=Decimal("0.20"),
        timestamp=app.datetime.now(app.UTC),
    )

    preflight = AsyncMock()
    preflight.run.return_value = SimpleNamespace(
        ready=True,
        blockers=[],
        quote_status={"XAUUSD": False},
    )

    with (
        patch.object(
            app,
            "RiskSettings",
            return_value=app.RiskSettings(
                trading_enabled=False,
            ),
        ),
        patch.object(
            app,
            "create_mt5_providers",
            new=AsyncMock(
                return_value=(
                    execution_provider,
                    market_data_provider,
                )
            ),
        ),
        patch.object(
            app,
            "MT5Preflight",
            return_value=preflight,
        ),
    ):
        result = await app.run_demo_order(
            side=app.OrderSide.BUY,
            dry_run=True,
        )

    assert result == 1
    market_data_provider.get_quote.assert_not_awaited()         