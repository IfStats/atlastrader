from unittest.mock import patch

from packages.core.config import IntelligenceSettings


def test_api_bootstrap_disables_intelligence_by_default() -> None:
    from apps.api.main import _build_intelligence_providers

    settings = IntelligenceSettings(enabled=False)

    assert _build_intelligence_providers(settings) == []


def test_api_bootstrap_requires_finnhub_credentials() -> None:
    from apps.api.main import _build_intelligence_providers

    settings = IntelligenceSettings(
        enabled=True,
        finnhub_api_key=None,
    )

    assert _build_intelligence_providers(settings) == []


def test_api_bootstrap_builds_finnhub_provider() -> None:
    from apps.api.main import _build_intelligence_providers

    settings = IntelligenceSettings(
        enabled=True,
        finnhub_api_key="test-key",
        finnhub_base_url="https://example.test/api",
        request_timeout_seconds=15.0,
        max_retries=4,
        retry_backoff_seconds=1.0,
    )

    with patch(
        "apps.api.main.FinnhubMarketIntelligenceProvider",
    ) as provider_class:
        provider = provider_class.return_value

        result = _build_intelligence_providers(settings)

    provider_class.assert_called_once_with(
        api_key="test-key",
        base_url="https://example.test/api",
        timeout_seconds=15.0,
        max_retries=4,
        backoff_seconds=1.0,
    )

    assert result == [provider]


def test_engine_bootstrap_disables_intelligence_by_default() -> None:
    from apps.engine.main import _build_intelligence_providers

    settings = IntelligenceSettings(enabled=False)

    assert _build_intelligence_providers(settings) == []


def test_engine_bootstrap_requires_finnhub_credentials() -> None:
    from apps.engine.main import _build_intelligence_providers

    settings = IntelligenceSettings(
        enabled=True,
        finnhub_api_key=None,
    )

    assert _build_intelligence_providers(settings) == []


def test_engine_bootstrap_builds_finnhub_provider() -> None:
    from apps.engine.main import _build_intelligence_providers

    settings = IntelligenceSettings(
        enabled=True,
        finnhub_api_key="test-key",
        finnhub_base_url="https://example.test/api",
        request_timeout_seconds=15.0,
        max_retries=4,
        retry_backoff_seconds=1.0,
    )

    with patch(
        "apps.engine.main.FinnhubMarketIntelligenceProvider",
    ) as provider_class:
        provider = provider_class.return_value

        result = _build_intelligence_providers(settings)

    provider_class.assert_called_once_with(
        api_key="test-key",
        base_url="https://example.test/api",
        timeout_seconds=15.0,
        max_retries=4,
        backoff_seconds=1.0,
    )

    assert result == [provider]