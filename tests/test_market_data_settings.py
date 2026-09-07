import pytest

from packages.core.config import (
    MassiveSettings,
    TwelveDataSettings,
)


def test_massive_settings_defaults() -> None:
    settings = MassiveSettings(
        _env_file=None,  # type: ignore[call-arg]
    )

    assert settings.enabled is False
    assert settings.api_key is None
    assert (
        settings.base_url
        == "https://api.massive.com"
    )
    assert settings.request_timeout_seconds == 10.0
    assert settings.max_retries == 2
    assert settings.retry_backoff_seconds == 0.5
    assert settings.has_credentials() is False


def test_massive_settings_detects_credentials() -> None:
    settings = MassiveSettings(
        api_key="test-key",
        _env_file=None,  # type: ignore[call-arg]
    )

    assert settings.has_credentials() is True


def test_massive_settings_rejects_blank_credentials() -> None:
    settings = MassiveSettings(
        api_key="   ",
        _env_file=None,  # type: ignore[call-arg]
    )

    assert settings.has_credentials() is False


def test_massive_settings_reads_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ATLAS_MASSIVE_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "ATLAS_MASSIVE_API_KEY",
        "environment-test-key",
    )
    monkeypatch.setenv(
        "ATLAS_MASSIVE_BASE_URL",
        "https://example.massive.test",
    )

    settings = MassiveSettings(
        _env_file=None,  # type: ignore[call-arg]
    )

    assert settings.enabled is True
    assert (
        settings.api_key
        == "environment-test-key"
    )
    assert (
        settings.base_url
        == "https://example.massive.test"
    )
    assert settings.has_credentials() is True


def test_twelve_data_settings_defaults() -> None:
    settings = TwelveDataSettings(
        _env_file=None,  # type: ignore[call-arg]
    )

    assert settings.enabled is False
    assert settings.api_key is None
    assert (
        settings.base_url
        == "https://api.twelvedata.com"
    )
    assert settings.request_timeout_seconds == 10.0
    assert settings.max_retries == 2
    assert settings.retry_backoff_seconds == 0.5
    assert settings.has_credentials() is False


def test_twelve_data_settings_detects_credentials() -> None:
    settings = TwelveDataSettings(
        api_key="test-key",
        _env_file=None,  # type: ignore[call-arg]
    )

    assert settings.has_credentials() is True


def test_twelve_data_settings_rejects_blank_credentials() -> None:
    settings = TwelveDataSettings(
        api_key="   ",
        _env_file=None,  # type: ignore[call-arg]
    )

    assert settings.has_credentials() is False


@pytest.mark.parametrize(
    ("settings_type", "kwargs"),
    [
        (
            MassiveSettings,
            {
                "request_timeout_seconds": 0,
            },
        ),
        (
            TwelveDataSettings,
            {
                "request_timeout_seconds": 0,
            },
        ),
        (
            MassiveSettings,
            {
                "max_retries": -1,
            },
        ),
        (
            TwelveDataSettings,
            {
                "max_retries": 11,
            },
        ),
    ],
)
def test_market_data_settings_reject_invalid_values(
    settings_type: type[
        MassiveSettings | TwelveDataSettings
    ],
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        settings_type(
            **kwargs,
            _env_file=None,  # type: ignore[call-arg]
        )