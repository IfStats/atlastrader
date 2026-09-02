from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.core.config import RiskSettings
from packages.core.enums import AssetClass, OrderSide, OrderStatus, Timeframe
from packages.core.models import Instrument, MarketState
from packages.engine.service import DefaultTradingEngine
from packages.execution.mock import MockExecutionProvider
from packages.portfolio.service import PortfolioService
from packages.risk.manager import DefaultRiskManager
from packages.risk.position_sizer import DefaultPositionSizer
from packages.strategy.momentum import MomentumStrategy
from packages.strategy.service import StrategyService

NOW = datetime.now(UTC)


def make_instrument() -> Instrument:
    return Instrument(
        symbol="XAUUSD",
        name="Gold",
        asset_class=AssetClass.COMMODITY,
        tick_size=Decimal("0.01"),
        contract_size=Decimal(100),
        min_volume=Decimal("0.01"),
        volume_step=Decimal("0.01"),
        price_precision=2,
        volume_precision=2,
        created_at=NOW,
        updated_at=NOW,
    )


def make_market_state() -> MarketState:
    return MarketState(
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        timestamp=NOW,
        price=Decimal(3350),
        trend_score=0.80,
        momentum_score=0.80,
        volatility_score=0.50,
        volatility=Decimal(5),
        spread=Decimal("0.20"),
        is_tradeable=True,
    )


def make_engine(
    *,
    max_open_positions: int = 5,
) -> DefaultTradingEngine:
    settings = RiskSettings(
        trading_enabled=True,
        max_risk_per_trade=Decimal("0.01"),
        max_daily_loss=Decimal("0.03"),
        max_open_positions=max_open_positions,
        max_portfolio_exposure=Decimal("0.50"),
        min_risk_reward_ratio=Decimal("1.5"),
        max_spread=Decimal("5.0"),
    )

    strategy_service = StrategyService(
        [MomentumStrategy()]
    )

    risk_manager = DefaultRiskManager(settings)

    execution_provider = MockExecutionProvider(
        balance=Decimal(10000),
        instruments={
            "XAUUSD": make_instrument(),
        },
    )

    portfolio = PortfolioService(
        balance=Decimal(10000),
    )

    return DefaultTradingEngine(
        strategy_service=strategy_service,
        risk_manager=risk_manager,
        execution_provider=execution_provider,
        position_sizer=DefaultPositionSizer(),
        risk_settings=settings,
        portfolio=portfolio,
    )


@pytest.mark.asyncio
async def test_filled_order_creates_portfolio_position() -> None:
    engine = make_engine()

    await engine.execution_provider.connect()

    order = await engine.process_market_state(
        make_market_state(),
    )

    assert order is not None
    assert order.status is OrderStatus.FILLED

    position = engine.portfolio.get_position("XAUUSD")

    assert position is not None
    assert position.symbol == "XAUUSD"
    assert position.side is OrderSide.BUY

    # $10,000 equity × 1% risk = $100 risk.
    # $5 stop distance × 100 contract size = $500 risk per lot.
    # $100 / $500 = 0.20 lots.
    assert position.quantity == Decimal("0.20")
    assert position.entry_price == Decimal(3350)


@pytest.mark.asyncio
async def test_portfolio_open_positions_increases_after_filled_order() -> None:
    engine = make_engine()

    await engine.execution_provider.connect()

    before = engine.portfolio.snapshot()

    assert before.open_positions == 0

    await engine.process_market_state(
        make_market_state(),
    )

    after = engine.portfolio.snapshot()

    assert after.open_positions == 1


@pytest.mark.asyncio
async def test_engine_respects_max_open_positions() -> None:
    engine = make_engine(max_open_positions=1)

    await engine.execution_provider.connect()

    first_order = await engine.process_market_state(
        make_market_state(),
    )

    assert first_order is not None
    assert first_order.status is OrderStatus.FILLED
    assert engine.portfolio.snapshot().open_positions == 1

    second_order = await engine.process_market_state(
        make_market_state(),
    )

    assert second_order is None
    assert engine.portfolio.snapshot().open_positions == 1


@pytest.mark.asyncio
async def test_portfolio_position_has_correct_exposure() -> None:
    engine = make_engine()

    await engine.execution_provider.connect()

    await engine.process_market_state(
        make_market_state(),
    )

    snapshot = engine.portfolio.snapshot()

    assert snapshot.open_positions == 1
    assert snapshot.total_exposure == Decimal("670.00")


@pytest.mark.asyncio
async def test_engine_records_filled_buy_order_in_portfolio() -> None:
    portfolio = PortfolioService(
        balance=Decimal(10000),
    )

    engine = make_engine()
    engine.portfolio = portfolio

    await engine.execution_provider.connect()

    market_state = make_market_state()

    order = await engine.process_market_state(market_state)

    assert order is not None
    assert order.status is OrderStatus.FILLED

    position = portfolio.get_position("XAUUSD")

    assert position is not None
    assert position.side is OrderSide.BUY
    assert position.quantity == order.quantity
    assert position.entry_price == order.price
    assert position.current_price == order.price


@pytest.mark.asyncio
async def test_engine_portfolio_snapshot_reflects_filled_order() -> None:
    portfolio = PortfolioService(
        balance=Decimal(10000),
    )

    engine = make_engine()
    engine.portfolio = portfolio

    await engine.execution_provider.connect()

    market_state = make_market_state()

    order = await engine.process_market_state(market_state)

    assert order is not None
    assert order.price is not None

    snapshot = portfolio.snapshot()

    assert snapshot.open_positions == 1
    assert snapshot.total_exposure == (
        order.quantity * order.price
    )
    assert snapshot.unrealized_pnl == Decimal(0)
