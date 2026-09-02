from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from apps.api.main import app
from packages.core.enums import OrderSide, PositionStatus
from packages.core.models import Position
from packages.execution.mock import MockExecutionProvider
from packages.portfolio.service import PortfolioService
from packages.runtime.service import TradingRuntime


def make_runtime() -> TradingRuntime:
    """Build a broker-independent runtime for API tests."""

    provider = MockExecutionProvider(
        balance=Decimal(10000),
    )

    portfolio = PortfolioService(
        balance=Decimal(10000),
    )

    from packages.engine.scanner import DefaultMarketScanner
    from packages.portfolio.position_manager import PositionManager
    from packages.portfolio.reconciliation import (
        PortfolioReconciliationService,
    )

    position_manager = PositionManager(
        execution_provider=provider,
        portfolio=portfolio,
    )

    reconciliation = PortfolioReconciliationService(
        provider=provider,
        portfolio=portfolio,
    )

    scanner = DefaultMarketScanner.__new__(DefaultMarketScanner)

    runtime = TradingRuntime(
        execution_provider=provider,
        portfolio=portfolio,
        position_manager=position_manager,
        reconciliation=reconciliation,
        scanner=scanner,
        symbols=["XAUUSD", "EURUSD"],
        interval_seconds=60,
    )

    return runtime


def make_client() -> TestClient:
    """Create a test client with an injected runtime."""

    app.state.runtime = make_runtime()

    return TestClient(app)


def make_position() -> Position:
    """Create a deterministic test position."""

    now = datetime.now(UTC)

    return Position(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        status=PositionStatus.OPEN,
        quantity=Decimal("0.20"),
        entry_price=Decimal(3350),
        current_price=Decimal(3352),
        stop_loss=Decimal(3345),
        take_profit=Decimal(3360),
        opened_at=now,
    )


def test_health() -> None:
    client = make_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
    }


def test_status() -> None:
    client = make_client()

    response = client.get("/status")

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "stopped"
    assert payload["started"] is False
    assert payload["running"] is False
    assert payload["execution_connected"] is False
    assert payload["symbols"] == ["XAUUSD", "EURUSD"]
    assert payload["interval_seconds"] == 60



def test_start_runtime() -> None:
    runtime = make_runtime()
    runtime._started = True
    app.state.runtime = runtime

    client = TestClient(app)

    with (
        patch.object(
            runtime,
            "start",
            new_callable=AsyncMock,
        ) as start,
        patch.object(
            runtime.execution_provider,
            "is_connected",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        response = client.post("/runtime/start")

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "running"
    assert payload["started"] is True
    assert payload["running"] is True
    assert payload["execution_connected"] is True
    assert payload["symbols"] == ["XAUUSD", "EURUSD"]
    assert payload["interval_seconds"] == 60

    start.assert_awaited_once()



def test_start_runtime_is_idempotent() -> None:
    runtime = make_runtime()
    runtime._started = True
    app.state.runtime = runtime

    client = TestClient(app)

    with (
        patch.object(
            runtime,
            "start",
            new_callable=AsyncMock,
        ) as start,
        patch.object(
            runtime.execution_provider,
            "is_connected",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        response = client.post("/runtime/start")

    assert response.status_code == 200
    assert response.json()["running"] is True
    start.assert_awaited_once()



def test_start_runtime_failure_returns_standard_error() -> None:
    runtime = make_runtime()
    app.state.runtime = runtime

    client = TestClient(app)

    with patch.object(
        runtime,
        "start",
        new_callable=AsyncMock,
        side_effect=RuntimeError("broker unavailable"),
    ) as start:
        response = client.post("/runtime/start")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "RUNTIME_START_FAILED",
            "message": "Unable to start trading runtime.",
        },
    }

    start.assert_awaited_once()



def test_stop_runtime() -> None:
    runtime = make_runtime()
    runtime._started = False
    app.state.runtime = runtime

    client = TestClient(app)

    with (
        patch.object(
            runtime,
            "stop",
            new_callable=AsyncMock,
        ) as stop,
        patch.object(
            runtime.execution_provider,
            "is_connected",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        response = client.post("/runtime/stop")

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "stopped"
    assert payload["started"] is False
    assert payload["running"] is False
    assert payload["execution_connected"] is False
    assert payload["symbols"] == ["XAUUSD", "EURUSD"]
    assert payload["interval_seconds"] == 60

    stop.assert_awaited_once()



def test_stop_runtime_is_idempotent() -> None:
    runtime = make_runtime()
    runtime._started = False
    app.state.runtime = runtime

    client = TestClient(app)

    with (
        patch.object(
            runtime,
            "stop",
            new_callable=AsyncMock,
        ) as stop,
        patch.object(
            runtime.execution_provider,
            "is_connected",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        response = client.post("/runtime/stop")

    assert response.status_code == 200
    assert response.json()["running"] is False
    stop.assert_awaited_once()



def test_stop_runtime_failure_returns_standard_error() -> None:
    runtime = make_runtime()
    app.state.runtime = runtime

    client = TestClient(app)

    with patch.object(
        runtime,
        "stop",
        new_callable=AsyncMock,
        side_effect=RuntimeError("broker disconnect failed"),
    ) as stop:
        response = client.post("/runtime/stop")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "RUNTIME_STOP_FAILED",
            "message": "Unable to stop trading runtime.",
        },
    }

    stop.assert_awaited_once()



def test_reconcile_runtime() -> None:
    runtime = make_runtime()
    app.state.runtime = runtime

    client = TestClient(app)

    with patch.object(
        runtime,
        "reconcile",
        new_callable=AsyncMock,
    ) as reconcile:
        response = client.post("/runtime/reconcile")

    assert response.status_code == 200

    payload = response.json()

    assert payload["balance"] == "10000"
    assert payload["equity"] == "10000"
    assert payload["realized_pnl"] == "0"
    assert payload["unrealized_pnl"] == "0"
    assert payload["net_pnl"] == "0"
    assert payload["open_positions"] == 0
    assert payload["total_exposure"] == "0"
    assert payload["available_equity"] == "10000"
    assert payload["open_symbols"] == []

    reconcile.assert_awaited_once()



def test_reconcile_runtime_reflects_portfolio() -> None:
    runtime = make_runtime()
    runtime.portfolio.add_position(make_position())
    app.state.runtime = runtime

    client = TestClient(app)

    with patch.object(
        runtime,
        "reconcile",
        new_callable=AsyncMock,
    ) as reconcile:
        response = client.post("/runtime/reconcile")

    assert response.status_code == 200

    payload = response.json()

    assert payload["balance"] == "10000"
    assert payload["open_positions"] == 1
    assert payload["open_symbols"] == ["XAUUSD"]
    assert payload["total_exposure"] == "670.00"

    reconcile.assert_awaited_once()



def test_reconcile_runtime_failure_returns_standard_error() -> None:
    runtime = make_runtime()
    app.state.runtime = runtime

    client = TestClient(app)

    with patch.object(
        runtime,
        "reconcile",
        new_callable=AsyncMock,
        side_effect=RuntimeError("broker synchronization failed"),
    ) as reconcile:
        response = client.post("/runtime/reconcile")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "RUNTIME_RECONCILE_FAILED",
            "message": "Unable to reconcile trading portfolio.",
        },
    }

    reconcile.assert_awaited_once()


def test_portfolio() -> None:
    client = make_client()

    response = client.get("/portfolio")

    assert response.status_code == 200

    payload = response.json()

    assert payload["balance"] == "10000"
    assert payload["equity"] == "10000"
    assert payload["realized_pnl"] == "0"
    assert payload["unrealized_pnl"] == "0"
    assert payload["net_pnl"] == "0"
    assert payload["open_positions"] == 0
    assert payload["total_exposure"] == "0"
    assert payload["available_equity"] == "10000"
    assert payload["open_symbols"] == []


def test_positions_returns_empty_collection() -> None:
    client = make_client()

    response = client.get("/positions")

    assert response.status_code == 200
    assert response.json() == {
        "positions": [],
    }


def test_positions_returns_tracked_position() -> None:
    runtime = make_runtime()
    runtime.portfolio.add_position(make_position())
    app.state.runtime = runtime

    client = TestClient(app)

    response = client.get("/positions")

    assert response.status_code == 200

    payload = response.json()

    assert len(payload["positions"]) == 1
    assert payload["positions"][0]["symbol"] == "XAUUSD"
    assert payload["positions"][0]["side"] == "buy"
    assert payload["positions"][0]["status"] == "open"
    assert payload["positions"][0]["quantity"] == "0.20"
    assert payload["positions"][0]["entry_price"] == "3350"
    assert payload["positions"][0]["current_price"] == "3352"


def test_get_position() -> None:
    runtime = make_runtime()
    runtime.portfolio.add_position(make_position())
    app.state.runtime = runtime

    client = TestClient(app)

    response = client.get("/positions/xauusd")

    assert response.status_code == 200

    payload = response.json()

    assert payload["symbol"] == "XAUUSD"
    assert payload["quantity"] == "0.20"


def test_get_missing_position_returns_standard_error() -> None:
    client = make_client()

    response = client.get("/positions/XAUUSD")

    assert response.status_code == 404

    assert response.json() == {
        "error": {
            "code": "POSITION_NOT_FOUND",
            "message": "No tracked position exists for XAUUSD.",
        },
    }



def test_unexpected_error_returns_standard_error() -> None:
    runtime = make_runtime()
    app.state.runtime = runtime

    client = TestClient(
        app,
        raise_server_exceptions=False,
    )

    with patch.object(
        runtime.execution_provider,
        "is_connected",
        new_callable=AsyncMock,
        side_effect=RuntimeError("unexpected failure"),
    ):
        response = client.get("/status")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected internal error occurred.",
        },
    }


def test_runtime_metrics() -> None:
    runtime = make_runtime()
    app.state.runtime = runtime

    client = TestClient(app)

    response = client.get("/runtime/metrics")

    assert response.status_code == 200

    payload = response.json()

    assert payload["started_at"] is None
    assert payload["last_scan_at"] is None
    assert payload["last_successful_scan_at"] is None
    assert payload["last_reconciliation_at"] is None
    assert payload["last_error"] is None
    assert payload["scan_count"] == 0
    assert payload["successful_scan_count"] == 0
    assert payload["failed_scan_count"] == 0