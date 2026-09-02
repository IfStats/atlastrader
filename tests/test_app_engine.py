import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from apps.engine import main as app


def test_runtime_settings_defaults_to_xauusd() -> None:
    settings = app.RuntimeSettings(
        _env_file=None,  # type: ignore[call-arg]
    )

    assert settings.symbols == "XAUUSD"
    assert settings.get_symbols() == ["XAUUSD"]


def test_runtime_settings_parses_and_deduplicates_symbols() -> None:
    settings = app.RuntimeSettings(
        symbols="xauusd, EURUSD, xauusd, BTCUSD",
        _env_file=None,  # type: ignore[call-arg]
    )

    assert settings.get_symbols() == [
        "XAUUSD",
        "EURUSD",
        "BTCUSD",
    ]


def test_runtime_settings_rejects_empty_symbols() -> None:
    settings = app.RuntimeSettings(
        symbols=" , , ",
        _env_file=None,  # type: ignore[call-arg]
    )

    with pytest.raises(
        ValueError,
        match="No trading symbols configured",
    ):
        settings.get_symbols()


def test_mt5_settings_stores_connection_configuration() -> None:
    settings = app.MT5Settings(
        login=123456,
        password="secret",
        server="Test-Server",
        path="terminal64.exe",
        _env_file=None,  # type: ignore[call-arg]
    )

    assert settings.login == 123456
    assert settings.password == "secret"
    assert settings.server == "Test-Server"
    assert settings.path == "terminal64.exe"


@pytest.mark.asyncio
async def test_main_starts_and_stops_runtime() -> None:
    runtime = AsyncMock()

    with (
        patch.object(
            app,
            "RuntimeSettings",
            return_value=app.RuntimeSettings(
                symbols="XAUUSD",
                initial_balance=Decimal(10000),
                _env_file=None,  # type: ignore[call-arg]
            ),
        ),
        patch.object(
            app,
            "RiskSettings",
            return_value=app.RiskSettings(
                trading_enabled=False,
                _env_file=None,  # type: ignore[call-arg]
            ),
        ),
        patch.object(
            app,
            "MT5Settings",
            return_value=app.MT5Settings(
                _env_file=None,  # type: ignore[call-arg]
            ),
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
        _env_file=None,  # type: ignore[call-arg]
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
