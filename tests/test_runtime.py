import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from packages.core.models import Quote
from packages.engine.runner import MarketScannerRunner
from packages.engine.scanner import DefaultMarketScanner
from packages.execution.mock import MockExecutionProvider
from packages.market_data.base import MarketDataProvider
from packages.portfolio.position_manager import PositionManager
from packages.portfolio.reconciliation import PortfolioReconciliationService
from packages.portfolio.service import PortfolioService
from packages.runtime.service import TradingRuntime


def make_runtime(
    *,
    symbols: list[str] | None = None,
    market_data_provider: MarketDataProvider | None = None,
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
        market_data_provider=market_data_provider,
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


def make_quote(
    *,
    symbol: str = "XAUUSD",
    timestamp: datetime | None = None,
) -> Quote:
    return Quote(
        symbol=symbol,
        bid=Decimal("2500.00"),
        ask=Decimal("2500.20"),
        timestamp=timestamp or datetime.now(UTC),
    )


async def wait_for_quote_count(
    runtime: TradingRuntime,
    expected: int,
) -> None:
    for _ in range(100):
        if runtime.metrics().quote_count >= expected:
            return
        await asyncio.sleep(0)

    raise AssertionError(
        f"Expected quote_count >= {expected}, "
        f"received {runtime.metrics().quote_count}",
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
    assert metrics.last_quote_at is None
    assert metrics.last_error is None
    assert metrics.scan_count == 0
    assert metrics.successful_scan_count == 0
    assert metrics.failed_scan_count == 0
    assert metrics.quote_count == 0
    assert metrics.quote_stream_error_count == 0


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


@pytest.mark.asyncio
async def test_runtime_starts_quote_consumer() -> None:
    market_data_provider = AsyncMock(
        spec=MarketDataProvider,
    )
    scanner = AsyncMock(spec=DefaultMarketScanner)
    scanner.scan.return_value = {}

    stream_started = asyncio.Event()

    async def quote_stream(
        symbols: list[str],
        *,
        interval_seconds: float,
    ) -> AsyncIterator[Quote]:
        assert symbols == ["XAUUSD"]
        assert interval_seconds == 60

        stream_started.set()

        while True:
            await asyncio.sleep(60)
            yield make_quote()

    market_data_provider.stream_quotes.side_effect = quote_stream

    (
        runtime,
        _provider,
        _portfolio,
        _position_manager,
        _reconciliation,
        _scanner,
        _runner,
    ) = make_runtime(
        market_data_provider=market_data_provider,
    )

    runtime.scanner = scanner

    await runtime.start()

    await asyncio.wait_for(
        stream_started.wait(),
        timeout=1,
    )

    assert runtime.quote_stream_running is True
    market_data_provider.connect.assert_awaited_once()
    market_data_provider.subscribe_quotes.assert_awaited_once_with(
        ["XAUUSD"],
    )
    market_data_provider.stream_quotes.assert_called_once_with(
        ["XAUUSD"],
        interval_seconds=60,
    )

    await runtime.stop()


@pytest.mark.asyncio
async def test_runtime_quote_consumer_records_quotes() -> None:
    market_data_provider = AsyncMock(
        spec=MarketDataProvider,
    )
    scanner = AsyncMock(spec=DefaultMarketScanner)
    scanner.scan.return_value = {}

    first_timestamp = datetime(
        2026,
        9,
        2,
        11,
        0,
        tzinfo=UTC,
    )
    second_timestamp = datetime(
        2026,
        9,
        2,
        11,
        0,
        1,
        tzinfo=UTC,
    )

    stream_ready = asyncio.Event()

    async def quote_stream(
        symbols: list[str],
        *,
        interval_seconds: float,
    ) -> AsyncIterator[Quote]:
        yield make_quote(
            timestamp=first_timestamp,
        )
        yield make_quote(
            timestamp=second_timestamp,
        )

        stream_ready.set()

        while True:
            await asyncio.sleep(60)

    market_data_provider.stream_quotes.side_effect = quote_stream

    (
        runtime,
        _provider,
        _portfolio,
        _position_manager,
        _reconciliation,
        _scanner,
        _runner,
    ) = make_runtime(
        market_data_provider=market_data_provider,
    )

    runtime.scanner = scanner

    await runtime.start()

    await asyncio.wait_for(
        stream_ready.wait(),
        timeout=1,
    )

    await wait_for_quote_count(
        runtime,
        2,
    )

    metrics = runtime.metrics()

    assert metrics.quote_count == 2
    assert metrics.last_quote_at == second_timestamp
    assert metrics.quote_stream_error_count == 0

    await runtime.stop()


@pytest.mark.asyncio
async def test_runtime_quote_consumer_records_stream_error() -> None:
    market_data_provider = AsyncMock(
        spec=MarketDataProvider,
    )
    scanner = AsyncMock(spec=DefaultMarketScanner)
    scanner.scan.return_value = {}

    error_recorded = asyncio.Event()

    async def failing_quote_stream(
        symbols: list[str],
        *,
        interval_seconds: float,
    ) -> AsyncIterator[Quote]:
        raise RuntimeError("quote stream failed")
        yield make_quote()

    market_data_provider.stream_quotes.side_effect = failing_quote_stream

    (
        runtime,
        _provider,
        _portfolio,
        _position_manager,
        _reconciliation,
        _scanner,
        _runner,
    ) = make_runtime(
        market_data_provider=market_data_provider,
    )

    runtime.scanner = scanner

    await runtime.start()

    for _ in range(100):
        if runtime.metrics().quote_stream_error_count == 1:
            error_recorded.set()
            break
        await asyncio.sleep(0)

    await asyncio.wait_for(
        error_recorded.wait(),
        timeout=1,
    )

    metrics = runtime.metrics()

    assert metrics.quote_stream_error_count == 1
    assert metrics.last_error == "quote stream failed"
    assert metrics.quote_count == 0
    assert runtime.quote_stream_running is False

    await runtime.stop()


@pytest.mark.asyncio
async def test_runtime_does_not_duplicate_quote_consumer() -> None:
    market_data_provider = AsyncMock(
        spec=MarketDataProvider,
    )
    scanner = AsyncMock(spec=DefaultMarketScanner)
    scanner.scan.return_value = {}

    stream_started = asyncio.Event()

    async def quote_stream(
        symbols: list[str],
        *,
        interval_seconds: float,
    ) -> AsyncIterator[Quote]:
        stream_started.set()

        while True:
            await asyncio.sleep(60)
            yield make_quote()

    market_data_provider.stream_quotes.side_effect = quote_stream

    (
        runtime,
        _provider,
        _portfolio,
        _position_manager,
        _reconciliation,
        _scanner,
        _runner,
    ) = make_runtime(
        market_data_provider=market_data_provider,
    )

    runtime.scanner = scanner

    await runtime.start()

    await asyncio.wait_for(
        stream_started.wait(),
        timeout=1,
    )

    first_quote_task = runtime._quote_task

    await runtime.start()

    assert runtime._quote_task is first_quote_task
    assert market_data_provider.stream_quotes.call_count == 1

    await runtime.stop()


@pytest.mark.asyncio
async def test_runtime_stop_cancels_quote_consumer_before_disconnect() -> None:
    market_data_provider = AsyncMock(
        spec=MarketDataProvider,
    )
    scanner = AsyncMock(spec=DefaultMarketScanner)
    scanner.scan.return_value = {}

    stream_cancelled = asyncio.Event()

    async def quote_stream(
        symbols: list[str],
        *,
        interval_seconds: float,
    ) -> AsyncIterator[Quote]:
        try:
            while True:
                await asyncio.sleep(60)
                yield make_quote()
        finally:
            stream_cancelled.set()

    market_data_provider.stream_quotes.side_effect = quote_stream

    calls: list[str] = []

    async def unsubscribe_quotes(
        symbols: list[str],
    ) -> None:
        calls.append("unsubscribe")

    async def disconnect() -> None:
        calls.append("disconnect")

    market_data_provider.unsubscribe_quotes.side_effect = (
        unsubscribe_quotes
    )
    market_data_provider.disconnect.side_effect = disconnect

    (
        runtime,
        _provider,
        _portfolio,
        _position_manager,
        _reconciliation,
        _scanner,
        _runner,
    ) = make_runtime(
        market_data_provider=market_data_provider,
    )

    runtime.scanner = scanner

    await runtime.start()
    await runtime.stop()

    assert stream_cancelled.is_set()
    assert runtime.quote_stream_running is False
    assert calls == [
        "unsubscribe",
        "disconnect",
    ]


@pytest.mark.asyncio
async def test_runtime_subscription_failure_cleans_up() -> None:
    market_data_provider = AsyncMock(
        spec=MarketDataProvider,
    )
    scanner = AsyncMock(spec=DefaultMarketScanner)

    market_data_provider.subscribe_quotes.side_effect = RuntimeError(
        "subscription failed",
    )

    (
        runtime,
        provider,
        _portfolio,
        _position_manager,
        _reconciliation,
        _scanner,
        runner,
    ) = make_runtime(
        market_data_provider=market_data_provider,
    )

    runtime.scanner = scanner

    with pytest.raises(
        RuntimeError,
        match="subscription failed",
    ):
        await runtime.start()

    assert await provider.is_connected() is False
    assert runtime._started is False
    assert runtime.quote_stream_running is False
    assert runner._task is None
    market_data_provider.stream_quotes.assert_not_called()
    market_data_provider.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_runtime_subscribes_before_starting_runner() -> None:
    market_data_provider = AsyncMock(
        spec=MarketDataProvider,
    )

    (
        runtime,
        _provider,
        _portfolio,
        _position_manager,
        _reconciliation,
        _scanner,
        runner,
    ) = make_runtime(
        market_data_provider=market_data_provider,
    )

    calls: list[str] = []

    async def subscribe_quotes(
        symbols: list[str],
    ) -> None:
        calls.append("subscribe")

    async def start_runner() -> None:
        calls.append("runner")

    market_data_provider.subscribe_quotes.side_effect = (
        subscribe_quotes
    )
    runner.start = AsyncMock(
        side_effect=start_runner,
    )

    await runtime.start()

    assert calls == [
        "subscribe",
        "runner",
    ]

    await runtime.stop()
