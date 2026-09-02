from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from packages.core.models import Order, Quote
from packages.engine.runner import MarketScannerRunner
from packages.engine.scanner import DefaultMarketScanner
from packages.execution.interfaces import ExecutionProvider
from packages.market_data.base import MarketDataProvider
from packages.market_data.service import MarketDataService
from packages.portfolio.position_manager import PositionManager
from packages.portfolio.reconciliation import PortfolioReconciliationService
from packages.portfolio.service import PortfolioService
from packages.runtime.models import RuntimeMetrics


class TradingRuntime:
    """Application runtime coordinating AtlasTrader services."""

    def __init__(
        self,
        *,
        execution_provider: ExecutionProvider,
        portfolio: PortfolioService,
        position_manager: PositionManager,
        reconciliation: PortfolioReconciliationService,
        scanner: DefaultMarketScanner,
        symbols: list[str],
        interval_seconds: float = 5.0,
        market_data_provider: MarketDataProvider | None = None,
        quote_stream_provider: MarketDataService | None = None,
    ) -> None:
        if not symbols:
            raise ValueError("At least one symbol is required")

        if interval_seconds <= 0:
            raise ValueError(
                "interval_seconds must be greater than zero"
            )

        self.execution_provider = execution_provider
        self.market_data_provider = market_data_provider
        self.quote_stream_provider = quote_stream_provider
        self.portfolio = portfolio
        self.position_manager = position_manager
        self.reconciliation = reconciliation
        self.scanner = scanner
        self.symbols = list(dict.fromkeys(symbols))
        self.interval_seconds = interval_seconds

        self.runner = MarketScannerRunner(
            scanner=scanner,
            symbols=self.symbols,
            interval_seconds=interval_seconds,
        )

        self._started = False
        self._market_data_subscribed = False
        self._quote_task: asyncio.Task[None] | None = None

        self._started_at: datetime | None = None
        self._last_scan_at: datetime | None = None
        self._last_successful_scan_at: datetime | None = None
        self._last_reconciliation_at: datetime | None = None
        self._last_quote_at: datetime | None = None
        self._last_error: str | None = None

        self._scan_count = 0
        self._successful_scan_count = 0
        self._failed_scan_count = 0
        self._quote_count = 0
        self._quote_stream_error_count = 0

    @property
    def started(self) -> bool:
        """Return whether the runtime has been started."""
        return self._started

    @property
    def is_running(self) -> bool:
        """Return whether the runtime is currently running."""
        return self._started

    @property
    def quote_stream_running(self) -> bool:
        """Return whether the live quote consumer is running."""
        return (
            self._quote_task is not None
            and not self._quote_task.done()
        )

    def metrics(self) -> RuntimeMetrics:
        """Return a snapshot of runtime operational telemetry."""
        return RuntimeMetrics(
            started_at=self._started_at,
            last_scan_at=self._last_scan_at,
            last_successful_scan_at=self._last_successful_scan_at,
            last_reconciliation_at=self._last_reconciliation_at,
            last_quote_at=self._last_quote_at,
            last_error=self._last_error,
            scan_count=self._scan_count,
            successful_scan_count=self._successful_scan_count,
            failed_scan_count=self._failed_scan_count,
            quote_count=self._quote_count,
            quote_stream_error_count=self._quote_stream_error_count,
        )

    async def start(self) -> None:
        """Connect providers, synchronize state, subscribe, and start services."""
        if self._started:
            return

        try:
            await self.execution_provider.connect()

            if self.market_data_provider is not None:
                await self.market_data_provider.connect()

            await self.position_manager.sync_all()

            if self.market_data_provider is not None:
                await self.market_data_provider.subscribe_quotes(
                    self.symbols,
                )
                self._market_data_subscribed = True

            await self.runner.start()

            if self._quote_stream_source() is not None:
                self._start_quote_consumer()

            self._started = True
            self._started_at = datetime.now(UTC)
            self._last_error = None

        except Exception as exc:
            self._last_error = str(exc)

            await self._stop_quote_consumer()

            if (
                self.market_data_provider is not None
                and self._market_data_subscribed
            ):
                try:
                    await self.market_data_provider.unsubscribe_quotes(
                        self.symbols,
                    )
                finally:
                    self._market_data_subscribed = False

            if self.market_data_provider is not None:
                await self.market_data_provider.disconnect()

            await self.execution_provider.disconnect()
            raise

    async def stop(self) -> None:
        """Stop services, unsubscribe symbols, and disconnect providers."""
        if not self._started:
            return

        try:
            await self.runner.stop()
        except Exception as exc:
            self._last_error = str(exc)
            raise
        finally:
            try:
                await self._stop_quote_consumer()
            finally:
                try:
                    if (
                        self.market_data_provider is not None
                        and self._market_data_subscribed
                    ):
                        try:
                            await self.market_data_provider.unsubscribe_quotes(
                                self.symbols,
                            )
                        finally:
                            self._market_data_subscribed = False
                finally:
                    try:
                        if self.market_data_provider is not None:
                            await self.market_data_provider.disconnect()
                    finally:
                        try:
                            await self.execution_provider.disconnect()
                        finally:
                            self._started = False

    async def reconcile(
        self,
        symbols: list[str] | None = None,
    ) -> None:
        """Reconcile account and tracked positions with the broker."""
        symbols = self.symbols if symbols is None else symbols

        try:
            await self.reconciliation.reconcile(symbols)
        except Exception as exc:
            self._last_error = str(exc)
            raise

        self._last_reconciliation_at = datetime.now(UTC)
        self._last_error = None

    async def run_forever(self) -> None:
        """Start the runtime and keep it alive until cancelled."""
        await self.start()

        try:
            await asyncio.Event().wait()
        except (asyncio.CancelledError, KeyboardInterrupt):
            await self.stop()
            raise

    async def scan_once(self) -> dict[str, Order | None]:
        """Run one scanner cycle for the configured symbols."""
        self._scan_count += 1
        self._last_scan_at = datetime.now(UTC)

        try:
            result = await self.scanner.scan(self.symbols)
        except Exception as exc:
            self._failed_scan_count += 1
            self._last_error = str(exc)
            raise

        self._successful_scan_count += 1
        self._last_successful_scan_at = datetime.now(UTC)
        self._last_error = None

        return result

    def _quote_stream_source(
        self,
    ) -> MarketDataService | MarketDataProvider | None:
        """Return the configured live quote stream source."""
        if self.quote_stream_provider is not None:
            return self.quote_stream_provider

        return self.market_data_provider

    def _start_quote_consumer(self) -> None:
        """Start the live quote consumer in the background."""
        if self._quote_stream_source() is None:
            return

        if self.quote_stream_running:
            return

        self._quote_task = asyncio.create_task(
            self._consume_quotes(),
        )

    async def _stop_quote_consumer(self) -> None:
        """Stop the live quote consumer gracefully."""
        task = self._quote_task

        if task is None:
            return

        self._quote_task = None

        if task is asyncio.current_task():
            return

        if not task.done():
            task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _consume_quotes(self) -> None:
        """Consume live quotes and maintain runtime telemetry."""
        source = self._quote_stream_source()

        if source is None:
            return

        try:
            async for quote in source.stream_quotes(
                self.symbols,
                interval_seconds=self.interval_seconds,
            ):
                self._record_quote(quote)

        except asyncio.CancelledError:
            raise

        except (RuntimeError, ValueError) as exc:
            self._quote_stream_error_count += 1
            self._last_error = str(exc)

    def _record_quote(self, quote: Quote) -> None:
        """Record a successfully received live quote."""
        self._quote_count += 1
        self._last_quote_at = quote.timestamp