from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.config import RiskSettings
from packages.core.enums import (
    MarketStatus,
    SignalDirection,
    StrategyType,
    Timeframe,
)
from packages.core.models import MarketState, Signal
from packages.engine.service import DefaultTradingEngine
from packages.execution.interfaces import ExecutionProvider
from packages.portfolio.service import PortfolioService
from packages.risk.manager import DefaultRiskManager
from packages.risk.position_sizer import DefaultPositionSizer
from packages.strategy.service import StrategyService


def make_market_state(
    *,
    tradeable: bool = True,
) -> MarketState:
    return MarketState(
        symbol="XAUUSD",
        timestamp=datetime.now(UTC),
        timeframe=Timeframe.M5,
        price=Decimal(3350),
        trend_score=Decimal("0.90"),
        momentum_score=Decimal("0.90"),
        volatility_score=Decimal("0.50"),
        volatility=Decimal(5),
        spread=Decimal("0.20"),
        market_status=MarketStatus.OPEN,
        is_tradeable=tradeable,
    )


def make_signal(
    *,
    stop_loss: Decimal | None = Decimal(3345),
    take_profit: Decimal | None = Decimal(3360),
    risk_reward_ratio: float | None = 2.0,
) -> Signal:
    return Signal(
        symbol="XAUUSD",
        direction=SignalDirection.LONG,
        strategy=StrategyType.MOMENTUM,
        score=90,
        timestamp=datetime.now(UTC),
        timeframe=Timeframe.M5,
        entry_price=Decimal(3350),
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward_ratio=risk_reward_ratio,
        rationale=["Safety test"],
    )


def make_engine(
    execution: ExecutionProvider,
) -> DefaultTradingEngine:
    settings = RiskSettings(
        trading_enabled=True,
        max_risk_per_trade=Decimal("0.01"),
        max_daily_loss=Decimal("0.03"),
        max_open_positions=5,
        max_portfolio_exposure=Decimal("0.50"),
        min_risk_reward_ratio=Decimal("1.5"),
        max_spread=Decimal(5),
    )

    strategy = MagicMock()
    strategy.generate_signal.return_value = None

    strategy_service = StrategyService([strategy])

    portfolio = PortfolioService(
        balance=Decimal(10000),
    )

    return DefaultTradingEngine(
        strategy_service=strategy_service,
        risk_manager=DefaultRiskManager(settings),
        execution_provider=execution,
        position_sizer=DefaultPositionSizer(),
        risk_settings=settings,
        portfolio=portfolio,
        market_data_provider=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_engine_does_not_execute_when_market_is_not_tradeable() -> None:
    execution = AsyncMock(spec=ExecutionProvider)
    engine = make_engine(execution)

    engine.strategy_service.select_signal = MagicMock(
        return_value=make_signal(),
    )

    result = await engine.process_market_state(
        make_market_state(tradeable=False),
    )

    assert result is None
    execution.submit_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_engine_does_not_execute_signal_without_stop_loss() -> None:
    execution = AsyncMock(spec=ExecutionProvider)
    engine = make_engine(execution)

    engine.strategy_service.select_signal = MagicMock(
        return_value=make_signal(stop_loss=None),
    )

    result = await engine.process_market_state(
        make_market_state(),
    )

    assert result is None
    execution.submit_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_engine_does_not_execute_signal_without_take_profit() -> None:
    execution = AsyncMock(spec=ExecutionProvider)
    engine = make_engine(execution)

    engine.strategy_service.select_signal = MagicMock(
        return_value=make_signal(take_profit=None),
    )

    result = await engine.process_market_state(
        make_market_state(),
    )

    assert result is None
    execution.submit_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_engine_does_not_execute_signal_below_minimum_risk_reward() -> None:
    execution = AsyncMock(spec=ExecutionProvider)
    engine = make_engine(execution)

    engine.strategy_service.select_signal = MagicMock(
        return_value=make_signal(risk_reward_ratio=1.0),
    )

    result = await engine.process_market_state(
        make_market_state(),
    )

    assert result is None
    execution.submit_order.assert_not_awaited()