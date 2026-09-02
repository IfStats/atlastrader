from __future__ import annotations

from decimal import Decimal

from packages.core.config import MT5Settings, RiskSettings
from packages.core.enums import Timeframe
from packages.engine.scanner import DefaultMarketScanner
from packages.engine.service import DefaultTradingEngine
from packages.execution.interfaces import ExecutionProvider
from packages.execution.mt5 import MT5ExecutionProvider
from packages.market_data.base import MarketDataProvider
from packages.market_data.mt5 import MT5MarketDataProvider
from packages.market_data.service import MarketDataService
from packages.portfolio.position_manager import PositionManager
from packages.portfolio.reconciliation import PortfolioReconciliationService
from packages.portfolio.service import PortfolioService
from packages.risk.manager import DefaultRiskManager
from packages.risk.position_sizer import DefaultPositionSizer
from packages.runtime.service import TradingRuntime
from packages.strategy.momentum import MomentumStrategy
from packages.strategy.service import StrategyService


def create_runtime(
    *,
    symbols: list[str],
    settings: RiskSettings | None = None,
    mt5_settings: MT5Settings | None = None,
    execution_provider: ExecutionProvider | None = None,
    market_data_provider: MarketDataProvider | None = None,
    balance: Decimal = Decimal(0),
    timeframe: Timeframe = Timeframe.M5,
    candle_lookback: int = 20,
    interval_seconds: float = 5.0,
) -> TradingRuntime:
    """Construct the AtlasTrader application runtime."""

    if not symbols:
        raise ValueError("At least one symbol is required")

    settings = settings or RiskSettings()
    mt5_settings = mt5_settings or MT5Settings()

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
        else MT5MarketDataProvider()
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
    )

    strategy_service = StrategyService(
        [
            MomentumStrategy(),
        ]
    )

    risk_manager = DefaultRiskManager(settings)
    position_sizer = DefaultPositionSizer()

    engine = DefaultTradingEngine(
        strategy_service=strategy_service,
        risk_manager=risk_manager,
        execution_provider=execution,
        position_sizer=position_sizer,
        risk_settings=settings,
        portfolio=portfolio,
        market_data_provider=normalized_market_data,
    )

    scanner = DefaultMarketScanner(
        engine,
    )

    return TradingRuntime(
        execution_provider=execution,
        market_data_provider=market_data,
        quote_stream_provider=normalized_market_data,
        portfolio=portfolio,
        position_manager=position_manager,
        reconciliation=reconciliation,
        scanner=scanner,
        symbols=symbols,
        interval_seconds=interval_seconds,
    )