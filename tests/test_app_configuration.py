from decimal import Decimal

import pytest

from packages.core.config import MT5Settings, RiskSettings, RuntimeSettings


def test_runtime_settings_parses_single_symbol() -> None:
    settings = RuntimeSettings(
        symbols="XAUUSD",
        _env_file=None,  # type: ignore[call-arg]
    )
    assert settings.get_symbols() == ["XAUUSD"]


def test_runtime_settings_parses_multiple_symbols() -> None:
    settings = RuntimeSettings(
        symbols="XAUUSD,EURUSD,GBPUSD",
        _env_file=None,  # type: ignore[call-arg]
    )
    assert settings.get_symbols() == [
        "XAUUSD",
        "EURUSD",
        "GBPUSD",
    ]


def test_runtime_settings_strips_whitespace_and_deduplicates_symbols() -> None:
    settings = RuntimeSettings(
        symbols=" XAUUSD, EURUSD, XAUUSD , EURUSD ",
        _env_file=None,  # type: ignore[call-arg]
    )
    assert settings.get_symbols() == [
        "XAUUSD",
        "EURUSD",
    ]


def test_runtime_settings_rejects_empty_symbols() -> None:
    settings = RuntimeSettings(
        symbols="",
        _env_file=None,  # type: ignore[call-arg]
    )
    with pytest.raises(
        ValueError,
        match="No trading symbols configured",
    ):
        settings.get_symbols()


def test_runtime_settings_preserves_initial_balance() -> None:
    settings = RuntimeSettings(
        symbols="XAUUSD",
        initial_balance=Decimal(12500),
        _env_file=None,  # type: ignore[call-arg]
    )
    assert settings.initial_balance == Decimal(12500)


def test_risk_settings_defaults_are_safe() -> None:
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


def test_mt5_settings_can_be_constructed_without_credentials() -> None:
    settings = MT5Settings(
        _env_file=None,  # type: ignore[call-arg]
    )
    assert settings.login is None
    assert settings.password is None
    assert settings.server is None
    assert settings.path is None
