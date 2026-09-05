from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.core.config import RiskSettings
from packages.core.enums import (
    AssetClass,
    MarketStatus,
    OrderSide,
    SignalDirection,
    Timeframe,
)
from packages.core.models import Instrument, MarketState
from packages.engine.autonomous_decision import AutonomousDecisionEngine
from packages.engine.market_context import MarketContext
from packages.engine.service import DefaultTradingEngine
from packages.execution.mock import MockExecutionProvider
from packages.intelligence.impact import MarketImpactContext
from packages.portfolio.service import PortfolioService
from packages.risk.manager import DefaultRiskManager
from packages.risk.position_sizer import DefaultPositionSizer
from packages.strategy.momentum import MomentumStrategy
from packages.strategy.service import StrategyService


class FakeMarketContextProvider:
    def __init__(self, context: MarketContext) -> None:
        self.context = context
        self.requested_symbols: list[str] = []

    async def get_market_context(
        self,
        symbol: str,
    ) -> MarketContext:
        self.requested_symbols.append(symbol)
        return self.context


def make_market_state(
    *,
    symbol: str = "XAUUSD",
    direction: SignalDirection = SignalDirection.LONG,
) -> MarketState:
    if direction is SignalDirection.SHORT:
        trend_score = -0.80
        momentum_score = -0.80
    else:
        trend_score = 0.80
        momentum_score = 0.80

    return MarketState(
        symbol=symbol,
        timestamp=datetime.now(UTC),
        timeframe=Timeframe.M5,
        price=Decimal("4377.97"),
        trend_score=trend_score,
        momentum_score=momentum_score,
        volatility_score=0.01,
        volatility=Decimal("5.00"),
        spread=Decimal("0.10"),
        market_status=MarketStatus.OPEN,
        session="london",
        is_tradeable=True,
    )


def make_context(
    *,
    symbol: str = "XAUUSD",
    direction: SignalDirection = SignalDirection.LONG,
    event_risk_score: float = 0.0,
) -> MarketContext:
    market_state = make_market_state(
        symbol=symbol,
        direction=direction,
    )

    intelligence = MarketImpactContext(
        generated_at=datetime.now(UTC),
        impacts=[],
        event_risk_score=event_risk_score,
        high_impact_event_count=0,
        rationale=[],
    )

    combined_score = (
        0.80
        if direction is SignalDirection.LONG
        else -0.80
    )

    return MarketContext(
        market_state=market_state,
        intelligence=intelligence,
        combined_directional_score=combined_score,
        combined_confidence=0.90,
        direction=direction,
        is_tradeable=True,
        rationale=[],
    )


def make_engine(
    context: MarketContext,
) -> tuple[
    DefaultTradingEngine,
    FakeMarketContextProvider,
    MockExecutionProvider,
]:
    execution_provider = MockExecutionProvider()

    now = datetime.now(UTC)

    instrument = Instrument(
        symbol="XAUUSD",
        name="Gold",
        asset_class=AssetClass.METAL,
        broker_symbol="XAUUSD",
        tick_size=Decimal("0.01"),
        contract_size=Decimal(100),
        min_volume=Decimal("0.01"),
        max_volume=Decimal(100),
        volume_step=Decimal("0.01"),
        price_precision=2,
        volume_precision=2,
        enabled=True,
        created_at=now,
        updated_at=now,
    )

    execution_provider.add_instrument(instrument)

    portfolio = PortfolioService(
        balance=Decimal(10000),
    )

    risk_settings = RiskSettings(
        max_risk_per_trade=Decimal("0.01"),
        max_open_positions=5,
        max_daily_loss=Decimal("0.05"),
        min_risk_reward_ratio=Decimal("1.5"),
    )

    strategy_service = StrategyService(
        strategies=[MomentumStrategy()],
    )

    risk_manager = DefaultRiskManager(
        settings=risk_settings,
    )

    position_sizer = DefaultPositionSizer()

    context_provider = FakeMarketContextProvider(context)

    engine = DefaultTradingEngine(
        strategy_service=strategy_service,
        risk_manager=risk_manager,
        execution_provider=execution_provider,
        position_sizer=position_sizer,
        risk_settings=risk_settings,
        portfolio=portfolio,
        market_context_provider=context_provider,
        autonomous_decision_engine=AutonomousDecisionEngine(),
    )

    return engine, context_provider, execution_provider


@pytest.mark.asyncio
async def test_autonomous_symbol_executes_authorized_signal() -> None:
    context = make_context()

    engine, provider, execution_provider = make_engine(context)

    await execution_provider.connect()

    result = await engine.process_autonomous_symbol("XAUUSD")

    assert provider.requested_symbols == ["XAUUSD"]
    assert result is not None
    assert result.symbol == "XAUUSD"
    assert result.side is OrderSide.BUY


@pytest.mark.asyncio
async def test_autonomous_symbol_rejects_unauthorized_context() -> None:
    context = make_context(
        event_risk_score=0.90,
    )

    engine, provider, _ = make_engine(context)

    result = await engine.process_autonomous_symbol("XAUUSD")

    assert provider.requested_symbols == ["XAUUSD"]
    assert result is None


@pytest.mark.asyncio
async def test_autonomous_symbol_rejects_missing_strategy_signal() -> None:
    context = make_context()

    weak_market_state = context.market_state.model_copy(
        update={
            "momentum_score": 0.10,
            "trend_score": 0.10,
        }
    )

    context = context.model_copy(
        update={
            "market_state": weak_market_state,
        }
    )

    engine, _, _ = make_engine(context)

    result = await engine.process_autonomous_symbol("XAUUSD")

    assert result is None


@pytest.mark.asyncio
async def test_autonomous_symbol_rejects_direction_conflict() -> None:
    context = make_context(
        direction=SignalDirection.SHORT,
    )

    conflicting_market_state = context.market_state.model_copy(
        update={
            "trend_score": 0.80,
            "momentum_score": 0.80,
        }
    )

    context = context.model_copy(
        update={
            "market_state": conflicting_market_state,
        }
    )

    engine, _, _ = make_engine(context)

    result = await engine.process_autonomous_symbol("XAUUSD")

    assert result is None


@pytest.mark.asyncio
async def test_autonomous_symbol_requires_context_provider() -> None:
    context = make_context()

    engine, _, _ = make_engine(context)
    engine.market_context_provider = None

    with pytest.raises(
        RuntimeError,
        match="Market context provider is required",
    ):
        await engine.process_autonomous_symbol("XAUUSD")