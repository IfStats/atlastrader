from decimal import Decimal

import pytest

from packages.core.config import (
    MT5Settings,
    RiskSettings,
    RuntimeSettings,
)


def test_risk_settings_defaults() -> None:
    settings = RiskSettings(
        _env_file=None,  # type: ignore[call-arg]
    )

    assert settings.max_risk_per_trade == Decimal("0.01")
    assert settings.max_daily_loss == Decimal("0.03")
    assert settings.max_open_positions == 5
    assert settings.max_portfolio_exposure == Decimal("0.50")
    assert settings.min_risk_reward_ratio == Decimal("1.5")
    assert settings.max_spread == Decimal("5.0")
    assert settings.trading_enabled is False


def test_risk_settings_rejects_invalid_risk_per_trade() -> None:
    with pytest.raises(ValueError):
        RiskSettings(
            max_risk_per_trade=Decimal(0),
            _env_file=None,  # type: ignore[call-arg]
        )


def test_risk_settings_rejects_risk_above_limit() -> None:
    with pytest.raises(ValueError):
        RiskSettings(
            max_risk_per_trade=Decimal("0.06"),
            _env_file=None,  # type: ignore[call-arg]
        )


def test_mt5_settings_defaults() -> None:
    settings = MT5Settings(
        _env_file=None,  # type: ignore[call-arg]
    )

    assert settings.login is None
    assert settings.password is None
    assert settings.server is None
    assert settings.path is None
    assert settings.has_credentials() is False


def test_mt5_settings_detects_complete_credentials() -> None:
    settings = MT5Settings(
        login=123456,
        password="secret",
        server="Test-Server",
        _env_file=None,  # type: ignore[call-arg]
    )

    assert settings.has_credentials() is True


def test_mt5_settings_rejects_incomplete_credentials() -> None:
    settings = MT5Settings(
        login=123456,
        password="",
        server="Test-Server",
        _env_file=None,  # type: ignore[call-arg]
    )

    assert settings.has_credentials() is False


def test_runtime_settings_defaults() -> None:
    settings = RuntimeSettings(
        _env_file=None,  # type: ignore[call-arg]
    )

    assert settings.symbols == "XAUUSD"
    assert settings.initial_balance == Decimal(0)
    assert settings.scan_interval_seconds == 5.0
    assert settings.timeframe == "M5"
    assert settings.candle_lookback == 20


def test_runtime_settings_parses_symbols() -> None:
    settings = RuntimeSettings(
        symbols="xauusd, EURUSD, BTCUSD",
        _env_file=None,  # type: ignore[call-arg]
    )

    assert settings.get_symbols() == [
        "XAUUSD",
        "EURUSD",
        "BTCUSD",
    ]


def test_runtime_settings_deduplicates_symbols() -> None:
    settings = RuntimeSettings(
        symbols="XAUUSD,EURUSD,XAUUSD",
        _env_file=None,  # type: ignore[call-arg]
    )

    assert settings.get_symbols() == [
        "XAUUSD",
        "EURUSD",
    ]


def test_runtime_settings_rejects_empty_symbols() -> None:
    settings = RuntimeSettings(
        symbols=" , , ",
        _env_file=None,  # type: ignore[call-arg]
    )

    with pytest.raises(
        ValueError,
        match="No trading symbols configured",
    ):
        settings.get_symbols()


def test_runtime_settings_rejects_negative_balance() -> None:
    with pytest.raises(ValueError):
        RuntimeSettings(
            initial_balance=Decimal(-1),
            _env_file=None,  # type: ignore[call-arg]
        )


def test_runtime_settings_rejects_invalid_interval() -> None:
    with pytest.raises(ValueError):
        RuntimeSettings(
            scan_interval_seconds=0,
            _env_file=None,  # type: ignore[call-arg]
        )


def test_runtime_settings_rejects_invalid_candle_lookback() -> None:
    with pytest.raises(ValueError):
        RuntimeSettings(
            candle_lookback=1,
            _env_file=None,  # type: ignore[call-arg]
        )
