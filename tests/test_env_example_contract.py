from pathlib import Path

ENV_EXAMPLE = Path(".env.example")


def _env_keys() -> set[str]:
    """Return configuration keys declared in .env.example."""
    keys: set[str] = set()

    for raw_line in ENV_EXAMPLE.read_text(
        encoding="utf-8"
    ).splitlines():
        line = raw_line.strip()

        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        key, _ = line.split("=", 1)
        keys.add(key.strip())

    return keys


def test_env_example_contains_runtime_contract() -> None:
    keys = _env_keys()

    expected = {
        "ATLAS_SYMBOLS",
        "ATLAS_TIMEFRAME",
        "ATLAS_CANDLE_LOOKBACK",
        "ATLAS_SCAN_INTERVAL_SECONDS",
        "ATLAS_INITIAL_BALANCE",
        "ATLAS_TRADING_ENABLED",
        "ATLAS_MAX_RISK_PER_TRADE",
        "ATLAS_MAX_DAILY_LOSS",
        "ATLAS_MAX_OPEN_POSITIONS",
        "ATLAS_MAX_PORTFOLIO_EXPOSURE",
        "ATLAS_MIN_RISK_REWARD_RATIO",
        "ATLAS_MAX_SPREAD",
        "MT5_LOGIN",
        "MT5_PASSWORD",
        "MT5_SERVER",
        "MT5_PATH",
        "ATLAS_INTELLIGENCE_ENABLED",
        "ATLAS_INTELLIGENCE_FINNHUB_API_KEY",
        "ATLAS_MASSIVE_ENABLED",
        "ATLAS_MASSIVE_API_KEY",
        "ATLAS_MASSIVE_BASE_URL",
        "ATLAS_TWELVEDATA_ENABLED",
        "ATLAS_TWELVEDATA_API_KEY",
        "ATLAS_TWELVEDATA_BASE_URL",
    }

    assert expected <= keys


def test_env_example_excludes_retired_configuration() -> None:
    keys = _env_keys()

    retired = {
        "ATLAS_INTERVAL_SECONDS",
        "ATLAS_MT5_LOGIN",
        "ATLAS_MT5_PASSWORD",
        "ATLAS_MT5_SERVER",
        "ATLAS_MT5_PATH",
        "ATLAS_POLYGON_ENABLED",
        "ATLAS_POLYGON_API_KEY",
        "ATLAS_POLYGON_BASE_URL",
        "ATLAS_POLYGON_REQUEST_TIMEOUT_SECONDS",
        "ATLAS_POLYGON_MAX_RETRIES",
        "ATLAS_POLYGON_RETRY_BACKOFF_SECONDS",
    }

    assert keys.isdisjoint(retired)