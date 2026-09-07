from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from packages.core.config import RiskSettings
from packages.core.enums import (
    AssetClass,
    MarketStatus,
    OrderStatus,
    SignalDirection,
    SignalStatus,
    StrategyType,
    Timeframe,
)
from packages.core.models import (
    Instrument,
    MarketState,
    Order,
    Signal,
)
from packages.engine.journal import (
    InMemoryTradeJournal,
)
from packages.engine.service import (
    DefaultTradingEngine,
)
from packages.execution.mock import (
    MockExecutionProvider,
)
from packages.portfolio.service import (
    PortfolioService,
)
from packages.strategy.service import (
    StrategyService,
)

NOW = datetime(
    2026,
    9,
    7,
    17,
    0,
    tzinfo=UTC,
)


class BrokerIdentityExecutionProvider(
    MockExecutionProvider
):
    """Mock execution provider that returns broker order identity."""

    async def submit_order(
        self,
        order: Order,
    ) -> Order:
        filled_order = await super().submit_order(
            order
        )

        return filled_order.model_copy(
            update={
                "broker_order_id": (
                    "broker-order-123"
                ),
            }
        )


def make_instrument() -> Instrument:
    return Instrument(
        symbol="XAUUSD",
        name="Gold",
        asset_class=AssetClass.METAL,
        quote_currency="USD",
        broker_symbol="XAUUSD",
        tick_size=Decimal("0.01"),
        contract_size=Decimal(100),
        min_volume=Decimal("0.01"),
        max_volume=Decimal(100),
        volume_step=Decimal("0.01"),
        price_precision=2,
        volume_precision=2,
        enabled=True,
        created_at=NOW,
        updated_at=NOW,
    )


def make_market_state() -> MarketState:
    return MarketState(
        symbol="XAUUSD",
        timestamp=NOW,
        timeframe=Timeframe.M5,
        price=Decimal("4377.97"),
        trend_score=0.8,
        momentum_score=0.9,
        volatility_score=0.4,
        volatility=Decimal(5),
        spread=Decimal("0.20"),
        market_status=MarketStatus.OPEN,
        session="london",
        is_tradeable=True,
    )


def make_signal() -> Signal:
    return Signal(
        symbol="XAUUSD",
        direction=SignalDirection.LONG,
        strategy=StrategyType.MOMENTUM,
        status=SignalStatus.CANDIDATE,
        score=85.0,
        timestamp=NOW,
        timeframe=Timeframe.M5,
        entry_price=Decimal("4377.97"),
        stop_loss=Decimal("4372.97"),
        take_profit=Decimal("4387.97"),
        risk_reward_ratio=2.0,
        rationale=[
            "Momentum threshold satisfied",
        ],
    )


def make_engine(
    *,
    journal: InMemoryTradeJournal | None,
    provider: MockExecutionProvider,
) -> DefaultTradingEngine:
    instrument = make_instrument()

    provider.add_instrument(
        instrument
    )

    risk_manager = MagicMock()
    risk_manager.approve_signal.return_value = True
    risk_manager.validate_order.return_value = True

    position_sizer = MagicMock()
    position_sizer.calculate_volume.return_value = (
        Decimal("0.01")
    )

    return DefaultTradingEngine(
        strategy_service=MagicMock(
            spec=StrategyService
        ),
        risk_manager=risk_manager,
        execution_provider=provider,
        position_sizer=position_sizer,
        risk_settings=RiskSettings(
            max_risk_per_trade=Decimal("0.01"),
            _env_file=None,  # type: ignore[call-arg]
        ),
        portfolio=PortfolioService(
            balance=Decimal(10000)
        ),
        journal=journal,
    )


@pytest.mark.asyncio
async def test_execution_attaches_broker_order_id_to_decision() -> None:
    journal = InMemoryTradeJournal()

    provider = BrokerIdentityExecutionProvider()

    engine = make_engine(
        journal=journal,
        provider=provider,
    )

    await provider.connect()

    result = await engine.execute_signal(
        make_signal(),
        make_market_state(),
    )

    assert result is not None
    assert result.status is OrderStatus.FILLED
    assert (
        result.broker_order_id
        == "broker-order-123"
    )

    decisions = list(
        journal._decisions.values()
    )

    assert len(decisions) == 1

    decision = decisions[0]

    assert decision.status == "approved"
    assert decision.order_id == result.id
    assert (
        decision.broker_order_id
        == "broker-order-123"
    )


@pytest.mark.asyncio
async def test_execution_without_broker_order_id_preserves_decision() -> None:
    journal = InMemoryTradeJournal()

    provider = MockExecutionProvider()

    engine = make_engine(
        journal=journal,
        provider=provider,
    )

    await provider.connect()

    result = await engine.execute_signal(
        make_signal(),
        make_market_state(),
    )

    assert result is not None
    assert result.status is OrderStatus.FILLED
    assert result.broker_order_id is None

    decisions = list(
        journal._decisions.values()
    )

    assert len(decisions) == 1

    decision = decisions[0]

    assert decision.order_id == result.id
    assert decision.broker_order_id is None


@pytest.mark.asyncio
async def test_execution_without_journal_preserves_behavior() -> None:
    provider = BrokerIdentityExecutionProvider()

    engine = make_engine(
        journal=None,
        provider=provider,
    )

    await provider.connect()

    result = await engine.execute_signal(
        make_signal(),
        make_market_state(),
    )

    assert result is not None
    assert result.status is OrderStatus.FILLED
    assert (
        result.broker_order_id
        == "broker-order-123"
    )