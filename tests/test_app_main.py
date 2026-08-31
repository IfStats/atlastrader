import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from apps.engine import main as app


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