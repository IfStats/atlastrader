from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from packages.core.config import RiskSettings
from packages.core.enums import OrderStatus, Timeframe
from packages.core.models import Instrument, MarketState, Signal
from packages.engine.service import DefaultTradingEngine
from packages.execution.mock import MockExecutionProvider
from packages.market_data.base import MarketDataProvider
from packages.risk.manager import DefaultRiskManager
from packages.strategy.momentum import MomentumStrategy
from packages.strategy.service import StrategyService

NOW = datetime.now(UTC)


def make_instrument() -> Instrument:
    return Instrument(
        symbol="XAUUSD",
        name="Gold",
        asset_class="commodity",
        tick_size=Decimal("0.01"),
        contract_size=Decimal(100),
        min_volume=Decimal("0.01"),
        volume_step=Decimal("0.01"),
        price_precision=2,
        volume_precision=2,
        created_at=NOW,
        updated_at=NOW,
    )


def make_market_state(
    *,
    symbol: str = "XAUUSD",
    is_tradeable: bool = True,
    momentum_score: float = 0.80,
    trend_score: float = 0.80,
) -> MarketState:
    return MarketState(
        symbol=symbol,
        timeframe=Timeframe.M5,
        timestamp=NOW,
        price=Decimal(3350),
        trend_score=trend_score,
        momentum_score=momentum_score,
        volatility_score=0.50,
        volatility=Decimal(5),
        spread=Decimal("0.20"),
        is_tradeable=is_tradeable,
    )


def make_engine(
    *,
    market_data_provider: MarketDataProvider | None = None,
) -> DefaultTradingEngine:
    strategy_service = StrategyService(
        [MomentumStrategy()]
    )

    risk_manager = DefaultRiskManager(
        RiskSettings(trading_enabled=True)
    )

    execution_provider = MockExecutionProvider(
        instruments={"XAUUSD": make_instrument()}
    )

    return DefaultTradingEngine(
        strategy_service=strategy_service,
        risk_manager=risk_manager,
        execution_provider=execution_provider,
        market_data_provider=market_data_provider,
    )


class RejectingRiskManager(DefaultRiskManager):
    """Risk manager that rejects every signal for engine tests."""

    def approve_signal(
        self,
        signal: Signal,
        market_state: MarketState,
        portfolio=None,
        **kwargs,
    ) -> bool:
        return False


@pytest.mark.asyncio
async def test_engine_returns_none_when_strategy_generates_no_signal() -> None:
    engine = make_engine()

    market_state = make_market_state(
        momentum_score=0.20,
        trend_score=0.20,
    )

    result = await engine.process_market_state(market_state)

    assert result is None


@pytest.mark.asyncio
async def test_engine_rejects_non_tradeable_market() -> None:
    engine = make_engine()

    market_state = make_market_state(
        is_tradeable=False,
    )

    result = await engine.process_market_state(market_state)

    assert result is None


@pytest.mark.asyncio
async def test_engine_requires_connected_execution_provider() -> None:
    engine = make_engine()

    market_state = make_market_state()

    with pytest.raises(RuntimeError, match="not connected"):
        await engine.process_market_state(market_state)


@pytest.mark.asyncio
async def test_engine_creates_and_executes_order() -> None:
    engine = make_engine()

    await engine.execution_provider.connect()

    market_state = make_market_state()

    order = await engine.process_market_state(market_state)

    assert order is not None
    assert order.symbol == "XAUUSD"
    assert order.status is OrderStatus.FILLED


@pytest.mark.asyncio
async def test_engine_rejects_signal_before_execution_when_risk_denies() -> None:
    strategy_service = StrategyService(
        [MomentumStrategy()]
    )

    risk_manager = RejectingRiskManager(
        RiskSettings(trading_enabled=True)
    )

    execution_provider = MockExecutionProvider(
        instruments={"XAUUSD": make_instrument()}
    )

    engine = DefaultTradingEngine(
        strategy_service=strategy_service,
        risk_manager=risk_manager,
        execution_provider=execution_provider,
    )

    await execution_provider.connect()

    market_state = make_market_state()

    result = await engine.process_market_state(market_state)

    assert result is None


@pytest.mark.asyncio
async def test_engine_rejects_order_when_execution_instrument_is_missing() -> None:
    engine = DefaultTradingEngine(
        strategy_service=StrategyService(
            [MomentumStrategy()]
        ),
        risk_manager=DefaultRiskManager(
            RiskSettings(trading_enabled=True)
        ),
        execution_provider=MockExecutionProvider(),
    )

    await engine.execution_provider.connect()

    market_state = make_market_state()

    with pytest.raises(KeyError, match="Instrument not found"):
        await engine.process_market_state(market_state)


@pytest.mark.asyncio
async def test_engine_process_symbol_fetches_market_state() -> None:
    provider = AsyncMock(spec=MarketDataProvider)

    market_state = make_market_state()

    provider.get_market_state.return_value = market_state

    engine = make_engine(
        market_data_provider=provider,
    )

    await engine.execution_provider.connect()

    order = await engine.process_symbol("XAUUSD")

    provider.get_market_state.assert_awaited_once_with("XAUUSD")

    assert order is not None
    assert order.symbol == "XAUUSD"
    assert order.status is OrderStatus.FILLED


@pytest.mark.asyncio
async def test_engine_process_symbol_returns_none_for_non_tradeable_market() -> None:
    provider = AsyncMock(spec=MarketDataProvider)

    provider.get_market_state.return_value = make_market_state(
        is_tradeable=False,
    )

    engine = make_engine(
        market_data_provider=provider,
    )

    await engine.execution_provider.connect()

    result = await engine.process_symbol("XAUUSD")

    provider.get_market_state.assert_awaited_once_with("XAUUSD")
    assert result is None


@pytest.mark.asyncio
async def test_engine_process_symbol_requires_market_data_provider() -> None:
    engine = make_engine()

    with pytest.raises(
        RuntimeError,
        match="Market data provider is not configured",
    ):
        await engine.process_symbol("XAUUSD")


@pytest.mark.asyncio
async def test_engine_process_symbol_propagates_market_data_error() -> None:
    provider = AsyncMock(spec=MarketDataProvider)

    provider.get_market_state.side_effect = RuntimeError(
        "Market data unavailable"
    )

    engine = make_engine(
        market_data_provider=provider,
    )

    with pytest.raises(
        RuntimeError,
        match="Market data unavailable",
    ):
        await engine.process_symbol("XAUUSD")

    provider.get_market_state.assert_awaited_once_with("XAUUSD")


def test_build_market_state() -> None:
    engine = make_engine()

    state = engine.build_market_state(
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        price=Decimal(3350),
        trend_score=0.80,
        momentum_score=0.80,
        volatility_score=0.50,
        volatility=Decimal(5),
        spread=Decimal("0.20"),
        is_tradeable=True,
    )

    assert state.symbol == "XAUUSD"
    assert state.timeframe is Timeframe.M5
    assert state.price == Decimal(3350)
    assert state.is_tradeable is True