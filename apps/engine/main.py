from __future__ import annotations

import asyncio

from packages.core.config import MT5Settings, RiskSettings, RuntimeSettings
from packages.runtime.factory import create_runtime
from packages.runtime.service import TradingRuntime


async def main() -> None:
    """Build, start, and maintain the AtlasTrader runtime."""

    runtime_settings = RuntimeSettings()
    risk_settings = RiskSettings()
    mt5_settings = MT5Settings()

    symbols = runtime_settings.get_symbols()

    runtime: TradingRuntime = create_runtime(
        symbols=symbols,
        settings=risk_settings,
        mt5_settings=mt5_settings,
        balance=runtime_settings.initial_balance,
    )

    try:
        await runtime.start()
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        return
    finally:
        await runtime.stop()


if __name__ == "__main__":
    asyncio.run(main())