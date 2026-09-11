from unittest.mock import patch

import pytest

from apps.engine.main import create_mt5_providers
from packages.core.config import MT5Settings


@pytest.mark.asyncio
async def test_create_mt5_providers_applies_server_utc_offset() -> None:
    settings = MT5Settings(
        login=123456,
        password="test-password",
        server="Test-Server",
        path="terminal64.exe",
        server_utc_offset_hours=3.0,
        _env_file=None,  # type: ignore[call-arg]
    )

    with (
        patch(
            "apps.engine.main.MT5Settings",
            return_value=settings,
        ),
        patch(
            "apps.engine.main.MT5ExecutionProvider",
        ) as execution_class,
        patch(
            "apps.engine.main.MT5MarketDataProvider",
        ) as market_data_class,
    ):
        execution, market_data = (
            await create_mt5_providers()
        )

    execution_class.assert_called_once_with(
        login=123456,
        password="test-password",
        server="Test-Server",
        path="terminal64.exe",
    )

    market_data_class.assert_called_once_with(
        server_utc_offset_hours=3.0,
    )

    assert execution is execution_class.return_value
    assert market_data is market_data_class.return_value