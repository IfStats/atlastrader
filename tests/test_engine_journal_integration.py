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
from packages.core.models import Instrument, MarketState, Signal
from packages.engine.journal import InMemoryTradeJournal
from packages.engine.service import DefaultTradingEngine
from packages.execution.mock import MockExecutionProvider
from packages.portfolio.service import PortfolioService
from packages.strategy.service import StrategyService

NOW = datetime.now(UTC)


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


def make_signal(
    *,
    entry_price: Decimal | None = Decimal("4377.97"),
    stop_loss: Decimal | None = Decimal("4372.97"),
    direction: SignalDirection = SignalDirection.LONG,
) -> Signal:
    return Signal(
        symbol="XAUUSD",
        direction=direction,
        strategy=StrategyType.MOMENTUM,
        status=SignalStatus.CANDIDATE,
        score=85.0,
        timestamp=NOW,
        timeframe=Timeframe.M5,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=Decimal("4387.97"),
        risk_reward_ratio=2.0,
        rationale=[
            "Momentum threshold satisfied",
            "Trend alignment confirmed",
        ],
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


def make_engine(
    *,
    journal: InMemoryTradeJournal | None = None,
    risk_manager: MagicMock | None = None,
    position_sizer: MagicMock | None = None,
    execution_provider: MockExecutionProvider | None = None,
) -> DefaultTradingEngine:
    instrument = make_instrument()

    if execution_provider is None:
        provider = MockExecutionProvider(
            instruments={"XAUUSD": instrument},
        )
    else:
        provider = execution_provider
        provider.add_instrument(instrument)

    if risk_manager is None:
        risk = MagicMock()
        risk.approve_signal.return_value = True
        risk.validate_order.return_value = True
    else:
        risk = risk_manager

    if position_sizer is None:
        sizer = MagicMock()
        sizer.calculate_volume.return_value = Decimal("0.01")
    else:
        sizer = position_sizer

    portfolio = PortfolioService(
        balance=Decimal(1000),
    )

    return DefaultTradingEngine(
        strategy_service=MagicMock(spec=StrategyService),
        risk_manager=risk,
        execution_provider=provider,
        position_sizer=sizer,
        risk_settings=RiskSettings(
            max_risk_per_trade=Decimal("0.01"),
        ),
        portfolio=portfolio,
        journal=journal,
    )


@pytest.mark.asyncio
async def test_approved_signal_is_recorded_in_journal() -> None:
    journal = InMemoryTradeJournal()
    engine = make_engine(journal=journal)
    signal = make_signal()
    market_state = make_market_state()

    order = engine._build_order(
        signal=signal,
        quantity=Decimal("0.01"),
    )

    engine._record_decision(
        signal=signal,
        market_state=market_state,
        decision=signal.direction,
        status="approved",
        rejection_reasons=[],
        decision_id="decision-approved",
        requested_quantity=Decimal("0.01"),
        order_id=order.id,
    )

    decision = journal.get_decision("decision-approved")

    assert decision is not None
    assert decision.symbol == "XAUUSD"
    assert decision.direction is SignalDirection.LONG
    assert decision.decision is SignalDirection.LONG
    assert decision.strategy is StrategyType.MOMENTUM
    assert decision.status == "approved"
    assert decision.signal_score == 85.0
    assert decision.order_id == order.id
    assert decision.requested_quantity == Decimal("0.01")
    assert decision.rejection_reasons == []


@pytest.mark.asyncio
async def test_risk_rejected_signal_is_recorded() -> None:
    journal = InMemoryTradeJournal()

    risk_manager = MagicMock()
    risk_manager.approve_signal.return_value = False

    engine = make_engine(
        journal=journal,
        risk_manager=risk_manager,
    )

    signal = make_signal()
    market_state = make_market_state()

    result = await engine.execute_signal(
        signal,
        market_state,
    )

    assert result is None

    decisions = list(journal._decisions.values())

    assert len(decisions) == 1

    decision = decisions[0]

    assert decision.status == "rejected"
    assert decision.decision is SignalDirection.LONG
    assert decision.rejection_reasons == [
        "risk_manager_rejected_signal"
    ]
    assert decision.order_id is None


@pytest.mark.asyncio
async def test_missing_entry_price_is_recorded() -> None:
    journal = InMemoryTradeJournal()
    engine = make_engine(journal=journal)

    signal = make_signal(entry_price=None)
    market_state = make_market_state()

    result = await engine.execute_signal(
        signal,
        market_state,
    )

    assert result is None

    decisions = list(journal._decisions.values())

    assert len(decisions) == 1

    decision = decisions[0]

    assert decision.status == "rejected"
    assert decision.direction is SignalDirection.LONG
    assert decision.decision is SignalDirection.FLAT
    assert decision.entry_price is None
    assert decision.rejection_reasons == [
        "missing_entry_price"
    ]


@pytest.mark.asyncio
async def test_missing_stop_loss_is_recorded() -> None:
    journal = InMemoryTradeJournal()
    engine = make_engine(journal=journal)

    signal = make_signal(stop_loss=None)
    market_state = make_market_state()

    result = await engine.execute_signal(
        signal,
        market_state,
    )

    assert result is None

    decisions = list(journal._decisions.values())

    assert len(decisions) == 1

    decision = decisions[0]

    assert decision.status == "rejected"
    assert decision.decision is SignalDirection.LONG
    assert decision.rejection_reasons == [
        "missing_stop_loss"
    ]


@pytest.mark.asyncio
async def test_zero_position_size_is_recorded() -> None:
    journal = InMemoryTradeJournal()

    position_sizer = MagicMock()
    position_sizer.calculate_volume.return_value = Decimal(0)

    engine = make_engine(
        journal=journal,
        position_sizer=position_sizer,
    )

    signal = make_signal()
    market_state = make_market_state()

    result = await engine.execute_signal(
        signal,
        market_state,
    )

    assert result is None

    decisions = list(journal._decisions.values())

    assert len(decisions) == 1

    decision = decisions[0]

    assert decision.status == "rejected"
    assert decision.decision is SignalDirection.LONG
    assert decision.rejection_reasons == [
        "position_size_zero"
    ]


@pytest.mark.asyncio
async def test_order_risk_rejection_is_recorded_with_order_id() -> None:
    journal = InMemoryTradeJournal()

    risk_manager = MagicMock()
    risk_manager.approve_signal.return_value = True
    risk_manager.validate_order.return_value = False

    engine = make_engine(
        journal=journal,
        risk_manager=risk_manager,
    )

    provider = engine.execution_provider
    await provider.connect()

    signal = make_signal()
    market_state = make_market_state()

    result = await engine.execute_signal(
        signal,
        market_state,
    )

    assert result is not None
    assert result.status is OrderStatus.REJECTED

    decisions = list(journal._decisions.values())

    assert len(decisions) == 1

    decision = decisions[0]

    assert decision.status == "rejected"
    assert decision.decision is SignalDirection.LONG
    assert decision.rejection_reasons == [
        "risk_manager_rejected_order"
    ]
    assert decision.order_id == result.id
    assert decision.requested_quantity == Decimal("0.01")


@pytest.mark.asyncio
async def test_successful_execution_records_approved_decision() -> None:
    journal = InMemoryTradeJournal()
    provider = MockExecutionProvider()

    engine = make_engine(
        journal=journal,
        execution_provider=provider,
    )

    await provider.connect()

    signal = make_signal()
    market_state = make_market_state()

    result = await engine.execute_signal(
        signal,
        market_state,
    )

    assert result is not None
    assert result.status is OrderStatus.FILLED

    decisions = list(journal._decisions.values())

    assert len(decisions) == 1

    decision = decisions[0]

    assert decision.status == "approved"
    assert decision.decision is SignalDirection.LONG
    assert decision.order_id == result.id
    assert decision.requested_quantity == Decimal("0.01")


@pytest.mark.asyncio
async def test_engine_without_journal_preserves_existing_behavior() -> None:
    engine = make_engine(journal=None)

    provider = engine.execution_provider
    await provider.connect()

    signal = make_signal()
    market_state = make_market_state()

    result = await engine.execute_signal(
        signal,
        market_state,
    )

    assert result is not None
    assert result.status is OrderStatus.FILLED