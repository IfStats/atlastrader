import asyncio
from collections.abc import Awaitable, Callable

from packages.core.models import Order
from packages.engine.service import DefaultTradingEngine
from packages.portfolio.instrument_registry import InstrumentRegistry


class DefaultMarketScanner:
    """Scans multiple instruments through the trading engine."""

    def __init__(
        self,
        engine: DefaultTradingEngine,
        *,
        registry: InstrumentRegistry | None = None,
        on_error: Callable[[str, Exception], Awaitable[None]] | None = None,
    ) -> None:
        self.engine = engine
        self.registry = registry
        self.on_error = on_error

    async def scan(
        self,
        symbols: list[str] | None = None,
    ) -> dict[str, Order | None]:
        """Process configured or explicitly supplied symbols concurrently."""

        if symbols is None:
            if self.registry is None:
                raise ValueError(
                    "symbols or an instrument registry is required"
                )

            symbols = self.registry.tradable_symbols()

        if not symbols:
            return {}

        if self.registry is not None:
            symbols = [
                symbol
                for symbol in symbols
                if self.registry.contains(symbol)
                and self.registry.is_enabled(symbol)
            ]

        unique_symbols = list(dict.fromkeys(symbols))

        async def process(
            symbol: str,
        ) -> tuple[str, Order | None]:
            try:
                order = await self.engine.process_symbol(symbol)
                return symbol, order
            except (KeyError, RuntimeError) as exc:
                if self.on_error is not None:
                    await self.on_error(symbol, exc)

                return symbol, None

        results = await asyncio.gather(
            *(process(symbol) for symbol in unique_symbols)
        )

        return dict(results)