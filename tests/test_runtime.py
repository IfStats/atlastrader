from datetime import UTC
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from packages.engine.runner import MarketScannerRunner
from packages.engine.scanner import DefaultMarketScanner
from packages.execution.mock import MockExecutionProvider
from packages.portfolio.position_manager import PositionManager
from packages.portfolio.reconciliation import PortfolioReconciliationService
from packages.portfolio.service import PortfolioService
from packages.runtime.service import TradingRuntime


def make_runtime(
    *,
    symbols: list[str] | None = None,
) -> tuple[
    TradingRuntime,
    MockExecutionProvider,
    PortfolioService,
    PositionManager,
    PortfolioReconciliationService,
    DefaultMarketScanner,
    MarketScannerRunner,
]:
    provider = MockExecutionProvider(
        balance=Decimal(10000),
    )

    portfolio = PortfolioService(
        balance=Decimal(10000),
    )

    position_manager = PositionManager(
        execution_provider=provider,
        portfolio=portfolio,
    )

    reconciliation = PortfolioReconciliationService(
        provider=provider,
        portfolio=portfolio,
    )

    scanner = AsyncMock(spec=DefaultMarketScanner)

    runtime = TradingRuntime(
        execution_provider=provider,
        portfolio=portfolio,
        position_manager=position_manager,
        reconciliation=reconciliation,
        scanner=scanner,
        symbols=symbols or ["XAUUSD"],
        interval_seconds=60,
    )

    return (
        runtime,
        provider,
        portfolio,
        position_manager,
        reconciliation,
        scanner,
        runtime.runner,
    )


def test_runtime_requires_symbols() -> None:
    provider = MockExecutionProvider()
    portfolio = PortfolioService(
        balance=Decimal(10000),
    )
    position_manager = PositionManager(
        execution_provider=provider,
        portfolio=portfolio,
    )
    reconciliation = PortfolioReconciliationService(
        provider=provider,
        portfolio=portfolio,
    )
    scanner = AsyncMock(spec=DefaultMarketScanner)

    with pytest.raises(
        ValueError,
        match="At least one symbol is required",
    ):
        TradingRuntime(
            execution_provider=provider,
            portfolio=portfolio,
            position_manager=position_manager,
            reconciliation=reconciliation,
            scanner=scanner,
            symbols=[],
        )
@pytest.mark.asyncio
async def test_runtime_starts() -> None:
    (
        runtime,
        provider,
        _portfolio,
        _position_manager,
        _reconciliation,
        scanner,
        _runner,
    ) = make_runtime()

    scanner.scan.return_value = {}

    await runtime.start()

    assert await provider.is_connected() is True
    assert runtime._started is True
    assert runtime.is_running is True

    await runtime.stop()

    assert await provider.is_connected() is False
    assert runtime._started is False
    assert runtime.is_running is False


@pytest.mark.asyncio
async def test_runtime_start_syncs_balance_and_positions() -> None:
    (
        runtime,
        provider,
        portfolio,
        _position_manager,
        _reconciliation,
        scanner,
        _runner,
    ) = make_runtime()

    provider._balance = Decimal(12500)
    scanner.scan.return_value = {}

    await runtime.start()

    assert portfolio.snapshot().balance == Decimal(12500)
    assert provider._connected is True

    await runtime.stop()


@pytest.mark.asyncio
async def test_runtime_does_not_start_twice() -> None:
    (
        runtime,
        _provider,
        _portfolio,
        _position_manager,
        _reconciliation,
        scanner,
        runner,
    ) = make_runtime()

    scanner.scan.return_value = {}

    await runtime.start()

    first_task = runner._task

    await runtime.start()

    assert runner._task is first_task

    await runtime.stop()


@pytest.mark.asyncio
async def test_runtime_start_failure_disconnects_provider() -> None:
    (
        runtime,
        provider,
        _portfolio,
        position_manager,
        _reconciliation,
        _scanner,
        _runner,
    ) = make_runtime()

    position_manager.sync_all = AsyncMock(
        side_effect=RuntimeError("Synchronization failed"),
    )

    with pytest.raises(
        RuntimeError,
        match="Synchronization failed",
    ):
        await runtime.start()

    assert await provider.is_connected() is False
    assert runtime._started is False


@pytest.mark.asyncio
async def test_runtime_stop_is_idempotent() -> None:
    (
        runtime,
        provider,
        _portfolio,
        _position_manager,
        _reconciliation,
        _scanner,
        _runner,
    ) = make_runtime()

    await runtime.stop()

    assert await provider.is_connected() is False

    await runtime.start()
    await runtime.stop()
    await runtime.stop()

    assert await provider.is_connected() is False
    assert runtime._started is False


@pytest.mark.asyncio
async def test_runtime_reconcile_delegates_to_reconciliation_service() -> None:
    (
        runtime,
        _provider,
        _portfolio,
        _position_manager,
        reconciliation,
        _scanner,
        _runner,
    ) = make_runtime()

    reconciliation.reconcile = AsyncMock()

    await runtime.reconcile(["XAUUSD", "EURUSD"])

    reconciliation.reconcile.assert_awaited_once_with(
        ["XAUUSD", "EURUSD"],
    )


@pytest.mark.asyncio
async def test_runtime_start_starts_runner_after_sync() -> None:
    (
        runtime,
        _provider,
        _portfolio,
        position_manager,
        _reconciliation,
        _scanner,
        runner,
    ) = make_runtime()

    position_manager.sync_all = AsyncMock()
    runner.start = AsyncMock()

    await runtime.start()

    position_manager.sync_all.assert_awaited_once()
    runner.start.assert_awaited_once()

    await runtime.stop()

@pytest.mark.asyncio
async def test_runtime_metrics_start_empty() -> None:
    (
        runtime,
        _provider,
        _portfolio,
        _position_manager,
        _reconciliation,
        _scanner,
        _runner,
    ) = make_runtime()

    metrics = runtime.metrics()

    assert metrics.started_at is None
    assert metrics.last_scan_at is None
    assert metrics.last_successful_scan_at is None
    assert metrics.last_reconciliation_at is None
    assert metrics.last_error is None
    assert metrics.scan_count == 0
    assert metrics.successful_scan_count == 0
    assert metrics.failed_scan_count == 0


@pytest.mark.asyncio
async def test_runtime_metrics_track_successful_scan() -> None:
    (
        runtime,
        _provider,
        _portfolio,
        _position_manager,
        _reconciliation,
        scanner,
        _runner,
    ) = make_runtime()

    scanner.scan.return_value = {
        "XAUUSD": None,
    }

    result = await runtime.scan_once()
    metrics = runtime.metrics()

    assert result == {
        "XAUUSD": None,
    }
    assert metrics.last_scan_at is not None
    assert metrics.last_successful_scan_at is not None
    assert metrics.last_error is None
    assert metrics.scan_count == 1
    assert metrics.successful_scan_count == 1
    assert metrics.failed_scan_count == 0


@pytest.mark.asyncio
async def test_runtime_metrics_track_failed_scan() -> None:
    (
        runtime,
        _provider,
        _portfolio,
        _position_manager,
        _reconciliation,
        scanner,
        _runner,
    ) = make_runtime()

    scanner.scan.side_effect = RuntimeError("scanner failed")

    with pytest.raises(
        RuntimeError,
        match="scanner failed",
    ):
        await runtime.scan_once()

    metrics = runtime.metrics()

    assert metrics.last_scan_at is not None
    assert metrics.last_successful_scan_at is None
    assert metrics.last_error == "scanner failed"
    assert metrics.scan_count == 1
    assert metrics.successful_scan_count == 0
    assert metrics.failed_scan_count == 1


@pytest.mark.asyncio
async def test_runtime_metrics_track_reconciliation() -> None:
    (
        runtime,
        _provider,
        _portfolio,
        _position_manager,
        reconciliation,
        _scanner,
        _runner,
    ) = make_runtime()

    reconciliation.reconcile = AsyncMock()

    await runtime.reconcile()

    metrics = runtime.metrics()

    assert metrics.last_reconciliation_at is not None
    assert metrics.last_error is None


@pytest.mark.asyncio
async def test_runtime_metrics_track_reconciliation_failure() -> None:
    (
        runtime,
        _provider,
        _portfolio,
        _position_manager,
        reconciliation,
        _scanner,
        _runner,
    ) = make_runtime()

    reconciliation.reconcile = AsyncMock(
        side_effect=RuntimeError("reconciliation failed"),
    )

    with pytest.raises(
        RuntimeError,
        match="reconciliation failed",
    ):
        await runtime.reconcile()

    metrics = runtime.metrics()

    assert metrics.last_reconciliation_at is None
    assert metrics.last_error == "reconciliation failed"


@pytest.mark.asyncio
async def test_runtime_metrics_track_start_time() -> None:
    (
        runtime,
        _provider,
        _portfolio,
        _position_manager,
        _reconciliation,
        scanner,
        _runner,
    ) = make_runtime()

    scanner.scan.return_value = {}

    assert runtime.metrics().started_at is None

    await runtime.start()

    metrics = runtime.metrics()

    assert metrics.started_at is not None
    assert metrics.started_at.tzinfo == UTC

    await runtime.stop()