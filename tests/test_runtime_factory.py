from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from packages.core.config import MT5Settings, RiskSettings
from packages.execution.interfaces import ExecutionProvider
from packages.market_data.base import MarketDataProvider
from packages.runtime.factory import create_runtime


def make_risk_settings() -> RiskSettings:
    return RiskSettings(
        trading_enabled=False,
    )


def test_factory_requires_symbols() -> None:
    with pytest.raises(
        ValueError,
        match="At least one symbol is required",
    ):
        create_runtime(
            symbols=[],
            settings=make_risk_settings(),
        )


def test_factory_uses_custom_execution_provider() -> None:
    execution = MagicMock(spec=ExecutionProvider)
    market_data = MagicMock(spec=MarketDataProvider)

    runtime = create_runtime(
        symbols=["XAUUSD"],
        settings=make_risk_settings(),
        execution_provider=execution,
        market_data_provider=market_data,
    )

    assert runtime.execution_provider is execution


def test_factory_uses_custom_market_data_provider() -> None:
    execution = MagicMock(spec=ExecutionProvider)
    market_data = MagicMock(spec=MarketDataProvider)

    runtime = create_runtime(
        symbols=["XAUUSD"],
        settings=make_risk_settings(),
        execution_provider=execution,
        market_data_provider=market_data,
    )

    assert runtime.market_data_provider is market_data


def test_factory_passes_mt5_settings_to_execution_provider() -> None:
    mt5_settings = MT5Settings(
        login=123456,
        password="test-password",
        server="Test-Server",
        path="terminal64.exe",
    )

    with patch(
        "packages.runtime.factory.MT5ExecutionProvider",
    ) as provider_class:
        execution = provider_class.return_value

        create_runtime(
            symbols=["XAUUSD"],
            settings=make_risk_settings(),
            mt5_settings=mt5_settings,
        )

    provider_class.assert_called_once_with(
        login=123456,
        password="test-password",
        server="Test-Server",
        path="terminal64.exe",
    )

    assert execution is not None


def test_factory_uses_default_mt5_settings_when_omitted() -> None:
    with patch(
        "packages.runtime.factory.MT5Settings",
        return_value=MT5Settings(
            login=123456,
            password="secret",
            server="Test-Server",
            path="terminal64.exe",
        ),
    ) as settings_class, patch(
        "packages.runtime.factory.MT5ExecutionProvider",
    ) as provider_class:
        create_runtime(
            symbols=["XAUUSD"],
            settings=make_risk_settings(),
        )

    settings_class.assert_called_once_with()

    provider_class.assert_called_once_with(
        login=123456,
        password="secret",
        server="Test-Server",
        path="terminal64.exe",
    )


def test_factory_preserves_initial_balance() -> None:
    execution = MagicMock(spec=ExecutionProvider)
    market_data = MagicMock(spec=MarketDataProvider)

    runtime = create_runtime(
        symbols=["XAUUSD"],
        settings=make_risk_settings(),
        execution_provider=execution,
        market_data_provider=market_data,
        balance=Decimal(10000),
    )

    assert runtime.portfolio.snapshot().balance == Decimal(10000)


def test_factory_deduplicates_symbols() -> None:
    execution = MagicMock(spec=ExecutionProvider)
    market_data = MagicMock(spec=MarketDataProvider)

    runtime = create_runtime(
        symbols=[
            "XAUUSD",
            "EURUSD",
            "XAUUSD",
        ],
        settings=make_risk_settings(),
        execution_provider=execution,
        market_data_provider=market_data,
    )

    assert runtime.symbols == [
        "XAUUSD",
        "EURUSD",
    ]


def test_factory_propagates_interval() -> None:
    execution = MagicMock(spec=ExecutionProvider)
    market_data = MagicMock(spec=MarketDataProvider)

    runtime = create_runtime(
        symbols=["XAUUSD"],
        settings=make_risk_settings(),
        execution_provider=execution,
        market_data_provider=market_data,
        interval_seconds=10.0,
    )

    assert runtime.interval_seconds == 10.0
    assert runtime.runner.interval_seconds == 10.0