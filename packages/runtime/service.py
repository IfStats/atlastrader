from __future__ import annotations

import asyncio

from packages.core.models import Order
from packages.engine.runner import MarketScannerRunner
from packages.engine.scanner import DefaultMarketScanner
from packages.execution.interfaces import ExecutionProvider
from packages.market_data.base import MarketDataProvider
from packages.portfolio.position_manager import PositionManager
from packages.portfolio.reconciliation import PortfolioReconciliationService
from packages.portfolio.service import PortfolioService


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
    ) -> None:
        if not symbols:
            raise ValueError("At least one symbol is required")

        if interval_seconds <= 0:
            raise ValueError(
                "interval_seconds must be greater than zero"
            )

        self.execution_provider = execution_provider
        self.market_data_provider = market_data_provider
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

    @property
    def started(self) -> bool:
        """Return whether the runtime has been started."""

        return self._started

    @property
    def is_running(self) -> bool:
        """Return whether the runtime is currently running."""

        return self._started

    async def start(self) -> None:
        """Connect providers, synchronize state, and start scanning."""

        if self._started:
            return

        await self.execution_provider.connect()

        try:
            if self.market_data_provider is not None:
                await self.market_data_provider.connect()

            await self.position_manager.sync_all()
            await self.runner.start()

            self._started = True

        except Exception:
            if self.market_data_provider is not None:
                await self.market_data_provider.disconnect()

            await self.execution_provider.disconnect()
            raise

    async def stop(self) -> None:
        """Stop scanning and disconnect providers."""

        if not self._started:
            return

        try:
            await self.runner.stop()
        finally:
            if self.market_data_provider is not None:
                await self.market_data_provider.disconnect()

            await self.execution_provider.disconnect()
            self._started = False

    async def reconcile(
        self,
        symbols: list[str] | None = None,
    ) -> None:
        """Reconcile account and tracked positions with the broker."""

        symbols = self.symbols if symbols is None else symbols

        await self.reconciliation.reconcile(symbols)

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

        return await self.scanner.scan(self.symbols)