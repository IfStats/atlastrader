import asyncio
from collections.abc import Awaitable, Callable, Mapping

from packages.core.models import Order
from packages.engine.scanner import DefaultMarketScanner


class MarketScannerRunner:
    """Continuously scans configured instruments."""

    def __init__(
        self,
        scanner: DefaultMarketScanner,
        symbols: list[str],
        *,
        interval_seconds: float = 5.0,
        on_cycle: (
            Callable[
                [Mapping[str, Order | None]],
                Awaitable[None],
            ]
            | None
        ) = None,
    ) -> None:
        if not symbols:
            raise ValueError("At least one symbol is required")

        if interval_seconds <= 0:
            raise ValueError(
                "interval_seconds must be greater than zero"
            )

        self.scanner = scanner
        self.symbols = list(dict.fromkeys(symbols))
        self.interval_seconds = interval_seconds
        self.on_cycle = on_cycle

        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    @property
    def is_running(self) -> bool:
        """Return whether the scanner loop is currently running."""

        return (
            self._task is not None
            and not self._task.done()
        )

    async def run(self) -> None:
        """Run the scanner continuously until stopped."""

        self._stop_event.clear()

        while not self._stop_event.is_set():
            results = await self.scanner.scan(self.symbols)

            if self.on_cycle is not None:
                await self.on_cycle(results)

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.interval_seconds,
                )
            except TimeoutError:
                continue

    async def start(self) -> None:
        """Start the scanner loop in the background."""

        if self.is_running:
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(self.run())

        await asyncio.sleep(0)

    async def stop(self) -> None:
        """Stop the scanner loop gracefully."""

        self._stop_event.set()

        task = self._task

        if task is None:
            return

        if task is asyncio.current_task():
            self._task = None
            return

        await task
        self._task = None