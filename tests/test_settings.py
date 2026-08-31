from decimal import Decimal

import pytest

from packages.core.enums import Timeframe
from packages.core.settings import MT5Settings, RuntimeSettings


def test_runtime_settings_defaults() -> None:
    settings = RuntimeSettings()

    assert settings.symbols == "XAUUSD"
    assert settings.timeframe is Timeframe.M5
    assert settings.candle_lookback == 20
    assert settings.interval_seconds == 5.0
    assert settings.initial_balance == Decimal(0)


def test_runtime_settings_parses_symbols() -> None:
    settings = RuntimeSettings(
        symbols="XAUUSD, EURUSD, GBPUSD, XAUUSD",
    )

    assert settings.symbol_list == [
        "XAUUSD",
        "EURUSD",
        "GBPUSD",
    ]


def test_runtime_settings_removes_empty_symbols() -> None:
    settings = RuntimeSettings(
        symbols=" XAUUSD, , EURUSD, ",
    )

    assert settings.symbol_list == [
        "XAUUSD",
        "EURUSD",
    ]


def test_runtime_settings_requires_valid_lookback() -> None:
    with pytest.raises(ValueError):
        RuntimeSettings(candle_lookback=1)


def test_runtime_settings_requires_positive_interval() -> None:
    with pytest.raises(ValueError):
        RuntimeSettings(interval_seconds=0)


def test_runtime_settings_requires_non_negative_balance() -> None:
    with pytest.raises(ValueError):
        RuntimeSettings(initial_balance=Decimal(-1))


def test_mt5_settings_defaults() -> None:
    settings = MT5Settings()

    assert settings.login is None
    assert settings.password is None
    assert settings.server is None
    assert settings.path is None