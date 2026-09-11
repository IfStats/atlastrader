from __future__ import annotations

from decimal import Decimal

from packages.core.config import (
    MassiveSettings,
    MT5Settings,
    RiskSettings,
    TwelveDataSettings,
)
from packages.core.enums import Timeframe
from packages.engine.market_context_provider import (
    DefaultMarketContextProvider,
)
from packages.engine.scanner import DefaultMarketScanner
from packages.engine.service import DefaultTradingEngine
from packages.execution.interfaces import ExecutionProvider
from packages.execution.mt5 import MT5ExecutionProvider
from packages.intelligence.gateway import (
    MarketIntelligenceGateway,
)
from packages.intelligence.interfaces import (
    MarketIntelligenceProvider,
)
from packages.market_data.base import MarketDataProvider
from packages.market_data.massive import (
    MassiveMarketDataProvider,
)
from packages.market_data.mt5 import MT5MarketDataProvider
from packages.market_data.observations import (
    ObservationalMarketDataProvider,
)
from packages.market_data.quality_service import (
    MarketDataQualityService,
)
from packages.market_data.service import MarketDataService
from packages.market_data.twelve_data import (
    TwelveDataObservationalProvider,
)
from packages.portfolio.position_manager import (
    PositionManager,
)
from packages.portfolio.reconciliation import (
    PortfolioReconciliationService,
)
from packages.portfolio.service import PortfolioService
from packages.risk.manager import DefaultRiskManager
from packages.risk.position_sizer import (
    DefaultPositionSizer,
)
from packages.runtime.service import (
    SecondaryMarketDataProvider,
    TradingRuntime,
)
from packages.strategy.momentum import MomentumStrategy
from packages.strategy.service import StrategyService


def create_runtime(
    *,
    symbols: list[str],
    settings: RiskSettings | None = None,
    mt5_settings: MT5Settings | None = None,
    massive_settings: MassiveSettings | None = None,
    twelve_data_settings: TwelveDataSettings | None = None,
    execution_provider: ExecutionProvider | None = None,
    market_data_provider: MarketDataProvider | None = None,
    intelligence_providers: (
        list[MarketIntelligenceProvider] | None
    ) = None,
    balance: Decimal = Decimal(0),
    timeframe: Timeframe = Timeframe.M5,
    candle_lookback: int = 20,
    interval_seconds: float = 5.0,
) -> TradingRuntime:
    """Construct the AtlasTrader application runtime."""

    if not symbols:
        raise ValueError(
            "At least one symbol is required"
        )

    settings = settings or RiskSettings()
    mt5_settings = mt5_settings or MT5Settings()
    massive_settings = (
        massive_settings or MassiveSettings()
    )
    twelve_data_settings = (
        twelve_data_settings
        or TwelveDataSettings()
    )

    if execution_provider is not None:
        execution = execution_provider
    else:
        execution = MT5ExecutionProvider(
            login=mt5_settings.login,
            password=mt5_settings.password,
            server=mt5_settings.server,
            path=mt5_settings.path,
        )

    market_data = (
        market_data_provider
        if market_data_provider is not None
        else MT5MarketDataProvider(
                server_utc_offset_hours=(
                    mt5_settings.server_utc_offset_hours

                ),
        )
    )

    (
        secondary_market_data_providers,
        market_data_quality_service,
    ) = _build_secondary_market_data(
        authoritative_provider=market_data,
        massive_settings=massive_settings,
        twelve_data_settings=twelve_data_settings,
    )

    portfolio = PortfolioService(
        balance=balance,
    )

    position_manager = PositionManager(
        execution_provider=execution,
        portfolio=portfolio,
    )

    reconciliation = PortfolioReconciliationService(
        provider=execution,
        portfolio=portfolio,
    )

    normalized_market_data = MarketDataService(
    market_data,
    timeframe=timeframe,
    candle_lookback=candle_lookback,
    market_data_quality_provider=(
        market_data_quality_service
        if not intelligence_providers
        else None
    ),
)

    strategy_service = StrategyService(
        [
            MomentumStrategy(),
        ]
    )

    risk_manager = DefaultRiskManager(
        settings
    )

    position_sizer = DefaultPositionSizer()

    if intelligence_providers:
        intelligence_gateway = (
            MarketIntelligenceGateway(
                providers=intelligence_providers,
            )
        )

        market_context_provider = (
            DefaultMarketContextProvider(
                market_data_service=(
                    normalized_market_data
                ),
                intelligence_gateway=(
                    intelligence_gateway
                ),
                market_data_quality_provider=(
                    market_data_quality_service
                ),
            )
        )

        engine = DefaultTradingEngine(
            strategy_service=strategy_service,
            risk_manager=risk_manager,
            execution_provider=execution,
            position_sizer=position_sizer,
            risk_settings=settings,
            portfolio=portfolio,
            market_data_provider=(
                normalized_market_data
            ),
            market_context_provider=(
                market_context_provider
            ),
        )

        scanner = DefaultMarketScanner(
            engine,
            autonomous=True,
        )

    else:
        engine = DefaultTradingEngine(
            strategy_service=strategy_service,
            risk_manager=risk_manager,
            execution_provider=execution,
            position_sizer=position_sizer,
            risk_settings=settings,
            portfolio=portfolio,
            market_data_provider=(
                normalized_market_data
            ),
        )

        scanner = DefaultMarketScanner(
            engine,
        )

    return TradingRuntime(
        execution_provider=execution,
        market_data_provider=market_data,
        secondary_market_data_providers=(
            secondary_market_data_providers
        ),
        intelligence_providers=(
            intelligence_providers
        ),
        quote_stream_provider=(
            normalized_market_data
        ),
        portfolio=portfolio,
        position_manager=position_manager,
        reconciliation=reconciliation,
        scanner=scanner,
        symbols=symbols,
        interval_seconds=interval_seconds,
    )


def _build_secondary_market_data(
    *,
    authoritative_provider: MarketDataProvider,
    massive_settings: MassiveSettings,
    twelve_data_settings: TwelveDataSettings,
) -> tuple[
    list[SecondaryMarketDataProvider],
    MarketDataQualityService | None,
]:
    """Construct configured secondary market-data providers."""

    secondary_providers: list[
        SecondaryMarketDataProvider
    ] = []

    reference_quote_providers: dict[
        str,
        MarketDataProvider,
    ] = {}

    observational_providers: dict[
        str,
        ObservationalMarketDataProvider,
    ] = {}

    massive_api_key = _enabled_api_key(
        provider_name="Massive",
        enabled=massive_settings.enabled,
        api_key=massive_settings.api_key,
    )

    if massive_api_key is not None:
        massive_provider = (
            MassiveMarketDataProvider(
                api_key=massive_api_key,
                base_url=(
                    massive_settings.base_url
                ),
                timeout_seconds=(
                    massive_settings
                    .request_timeout_seconds
                ),
                max_retries=(
                    massive_settings.max_retries
                ),
                backoff_seconds=(
                    massive_settings
                    .retry_backoff_seconds
                ),
            )
        )

        secondary_providers.append(
            massive_provider
        )

        reference_quote_providers[
            "Massive"
        ] = massive_provider

    twelve_data_api_key = _enabled_api_key(
        provider_name="Twelve Data",
        enabled=twelve_data_settings.enabled,
        api_key=twelve_data_settings.api_key,
    )

    if twelve_data_api_key is not None:
        twelve_data_provider = (
            TwelveDataObservationalProvider(
                api_key=twelve_data_api_key,
                base_url=(
                    twelve_data_settings.base_url
                ),
                timeout_seconds=(
                    twelve_data_settings
                    .request_timeout_seconds
                ),
                max_retries=(
                    twelve_data_settings
                    .max_retries
                ),
                backoff_seconds=(
                    twelve_data_settings
                    .retry_backoff_seconds
                ),
            )
        )

        secondary_providers.append(
            twelve_data_provider
        )

        observational_providers[
            "Twelve Data"
        ] = twelve_data_provider

    if not (
        reference_quote_providers
        or observational_providers
    ):
        return (
            secondary_providers,
            None,
        )

    quality_service = MarketDataQualityService(
        authoritative_source="MT5",
        authoritative_provider=(
            authoritative_provider
        ),
        reference_quote_providers=(
            reference_quote_providers
        ),
        observational_providers=(
            observational_providers
        ),
    )

    return (
        secondary_providers,
        quality_service,
    )


def _enabled_api_key(
    *,
    provider_name: str,
    enabled: bool,
    api_key: str | None,
) -> str | None:
    """Return a configured API key for an enabled provider."""

    if not enabled:
        return None

    normalized_api_key = (
        api_key or ""
    ).strip()

    if not normalized_api_key:
        raise ValueError(
            f"{provider_name} is enabled "
            "but API key is not configured"
        )

    return normalized_api_key