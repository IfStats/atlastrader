from unittest.mock import MagicMock, patch

import pytest

from packages.core.config import (
    MassiveSettings,
    RiskSettings,
    TwelveDataSettings,
)
from packages.execution.interfaces import (
    ExecutionProvider,
)
from packages.intelligence.interfaces import (
    MarketIntelligenceProvider,
)
from packages.market_data.base import (
    MarketDataProvider,
)
from packages.market_data.quality_service import (
    MarketDataQualityService,
)
from packages.runtime.factory import (
    create_runtime,
)


def make_risk_settings() -> RiskSettings:
    return RiskSettings(
        trading_enabled=False,
        _env_file=None,  # type: ignore[call-arg]
    )


def disabled_massive_settings() -> MassiveSettings:
    return MassiveSettings(
        enabled=False,
        _env_file=None,  # type: ignore[call-arg]
    )


def disabled_twelve_data_settings() -> TwelveDataSettings:
    return TwelveDataSettings(
        enabled=False,
        _env_file=None,  # type: ignore[call-arg]
    )


def make_dependencies() -> tuple[
    MagicMock,
    MagicMock,
    MagicMock,
]:
    execution = MagicMock(
        spec=ExecutionProvider
    )

    market_data = MagicMock(
        spec=MarketDataProvider
    )

    intelligence = MagicMock(
        spec=MarketIntelligenceProvider
    )

    return (
        execution,
        market_data,
        intelligence,
    )


def test_factory_has_no_secondary_quality_service_when_disabled() -> None:
    (
        execution,
        market_data,
        intelligence,
    ) = make_dependencies()

    runtime = create_runtime(
        symbols=["XAUUSD"],
        settings=make_risk_settings(),
        execution_provider=execution,
        market_data_provider=market_data,
        intelligence_providers=[
            intelligence
        ],
        massive_settings=(
            disabled_massive_settings()
        ),
        twelve_data_settings=(
            disabled_twelve_data_settings()
        ),
    )

    assert (
        runtime.secondary_market_data_providers
        == []
    )

    context_provider = (
        runtime.scanner.engine
        .market_context_provider
    )

    assert context_provider is not None

    assert (
        context_provider
        .market_data_quality_provider
        is None
    )


def test_factory_wires_massive_quality_provider() -> None:
    (
        execution,
        market_data,
        intelligence,
    ) = make_dependencies()

    massive_settings = MassiveSettings(
        enabled=True,
        api_key="massive-test-key",
        base_url="https://massive.test",
        request_timeout_seconds=7.0,
        max_retries=3,
        retry_backoff_seconds=0.25,
        _env_file=None,  # type: ignore[call-arg]
    )

    with patch(
        "packages.runtime.factory."
        "MassiveMarketDataProvider",
    ) as provider_class:
        provider = provider_class.return_value

        runtime = create_runtime(
            symbols=["XAUUSD"],
            settings=make_risk_settings(),
            execution_provider=execution,
            market_data_provider=market_data,
            intelligence_providers=[
                intelligence
            ],
            massive_settings=(
                massive_settings
            ),
            twelve_data_settings=(
                disabled_twelve_data_settings()
            ),
        )

    provider_class.assert_called_once_with(
        api_key="massive-test-key",
        base_url="https://massive.test",
        timeout_seconds=7.0,
        max_retries=3,
        backoff_seconds=0.25,
    )

    assert (
        runtime.secondary_market_data_providers
        == [provider]
    )

    context_provider = (
        runtime.scanner.engine
        .market_context_provider
    )

    assert context_provider is not None

    quality_service = (
        context_provider
        .market_data_quality_provider
    )

    assert isinstance(
        quality_service,
        MarketDataQualityService,
    )

    assert (
        quality_service.authoritative_provider
        is market_data
    )

    assert (
        quality_service.reference_quote_providers[
            "Massive"
        ]
        is provider
    )

    assert (
        quality_service.observational_providers
        == {}
    )


def test_factory_wires_twelve_data_observation_provider() -> None:
    (
        execution,
        market_data,
        intelligence,
    ) = make_dependencies()

    twelve_data_settings = TwelveDataSettings(
        enabled=True,
        api_key="twelve-test-key",
        base_url="https://twelve.test",
        request_timeout_seconds=8.0,
        max_retries=4,
        retry_backoff_seconds=0.30,
        _env_file=None,  # type: ignore[call-arg]
    )

    with patch(
        "packages.runtime.factory."
        "TwelveDataObservationalProvider",
    ) as provider_class:
        provider = provider_class.return_value

        runtime = create_runtime(
            symbols=["XAUUSD"],
            settings=make_risk_settings(),
            execution_provider=execution,
            market_data_provider=market_data,
            intelligence_providers=[
                intelligence
            ],
            massive_settings=(
                disabled_massive_settings()
            ),
            twelve_data_settings=(
                twelve_data_settings
            ),
        )

    provider_class.assert_called_once_with(
        api_key="twelve-test-key",
        base_url="https://twelve.test",
        timeout_seconds=8.0,
        max_retries=4,
        backoff_seconds=0.30,
    )

    assert (
        runtime.secondary_market_data_providers
        == [provider]
    )

    context_provider = (
        runtime.scanner.engine
        .market_context_provider
    )

    assert context_provider is not None

    quality_service = (
        context_provider
        .market_data_quality_provider
    )

    assert isinstance(
        quality_service,
        MarketDataQualityService,
    )

    assert (
        quality_service.observational_providers[
            "Twelve Data"
        ]
        is provider
    )

    assert (
        quality_service.reference_quote_providers
        == {}
    )


def test_factory_passes_intelligence_providers_to_runtime() -> None:
    (
        execution,
        market_data,
        intelligence,
    ) = make_dependencies()

    runtime = create_runtime(
        symbols=["XAUUSD"],
        settings=make_risk_settings(),
        execution_provider=execution,
        market_data_provider=market_data,
        intelligence_providers=[
            intelligence
        ],
        massive_settings=(
            disabled_massive_settings()
        ),
        twelve_data_settings=(
            disabled_twelve_data_settings()
        ),
    )

    assert runtime.intelligence_providers == [
        intelligence
    ]


def test_factory_rejects_enabled_massive_without_api_key() -> None:
    execution = MagicMock(
        spec=ExecutionProvider
    )

    market_data = MagicMock(
        spec=MarketDataProvider
    )

    with pytest.raises(
        ValueError,
        match=(
            "Massive is enabled "
            "but API key is not configured"
        ),
    ):
        create_runtime(
            symbols=["XAUUSD"],
            settings=make_risk_settings(),
            execution_provider=execution,
            market_data_provider=market_data,
            massive_settings=MassiveSettings(
                enabled=True,
                api_key=None,
                _env_file=None,  # type: ignore[call-arg]
            ),
            twelve_data_settings=(
                disabled_twelve_data_settings()
            ),
        )


def test_factory_rejects_enabled_twelve_data_without_api_key() -> None:
    execution = MagicMock(
        spec=ExecutionProvider
    )

    market_data = MagicMock(
        spec=MarketDataProvider
    )

    with pytest.raises(
        ValueError,
        match=(
            "Twelve Data is enabled "
            "but API key is not configured"
        ),
    ):
        create_runtime(
            symbols=["XAUUSD"],
            settings=make_risk_settings(),
            execution_provider=execution,
            market_data_provider=market_data,
            massive_settings=(
                disabled_massive_settings()
            ),
            twelve_data_settings=(
                TwelveDataSettings(
                    enabled=True,
                    api_key="   ",
                    _env_file=None,  # type: ignore[call-arg]
                )
            ),
        )

def test_secondary_quality_guards_non_autonomous_market_data() -> None:
    execution = MagicMock(
        spec=ExecutionProvider
    )

    market_data = MagicMock(
        spec=MarketDataProvider
    )

    massive_settings = MassiveSettings(
        enabled=True,
        api_key="massive-test-key",
        _env_file=None,  # type: ignore[call-arg]
    )

    with patch(
        "packages.runtime.factory."
        "MassiveMarketDataProvider",
    ):
        runtime = create_runtime(
            symbols=["XAUUSD"],
            settings=make_risk_settings(),
            execution_provider=execution,
            market_data_provider=market_data,
            intelligence_providers=None,
            massive_settings=massive_settings,
            twelve_data_settings=(
                disabled_twelve_data_settings()
            ),
        )

    assert runtime.scanner.autonomous is False

    normalized_market_data = (
        runtime.scanner.engine.market_data_provider
    )

    assert normalized_market_data is not None

    assert (
        normalized_market_data
        .market_data_quality_provider
        is not None
    )        