from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from packages.core.enums import (
    OrderSide,
    OrderStatus,
    SignalDirection,
    StrategyType,
    Timeframe,
)
from packages.core.trading_journal import TradeDecision, TradeOutcome
from packages.engine.journal import InMemoryTradeJournal

NOW = datetime.now(UTC)


def make_decision() -> TradeDecision:
    return TradeDecision(
        id="decision-001",
        symbol="XAUUSD",
        direction=SignalDirection.LONG,
        strategy=StrategyType.MOMENTUM,
        timeframe=Timeframe.M5,
        decision=SignalDirection.LONG,
        status="approved",
        timestamp=NOW,
        signal_score=82.5,
        confidence=0.82,
        entry_price=Decimal("4377.97"),
        stop_loss=Decimal("4372.97"),
        take_profit=Decimal("4387.97"),
        risk_reward_ratio=Decimal("2.0"),
        requested_quantity=Decimal("0.01"),
        risk_amount=Decimal("5.00"),
        risk_percentage=Decimal("0.0027"),
        rationale=["Bullish momentum confirmed"],
        rejection_reasons=[],
        market_state={
            "trend_score": 0.75,
            "momentum_score": 0.82,
            "volatility_score": 0.55,
        },
        order_id="order-001",
        created_at=NOW,
        updated_at=NOW,
    )


def make_outcome() -> TradeOutcome:
    opened_at = NOW
    closed_at = opened_at + timedelta(minutes=15)

    return TradeOutcome(
        trade_id="trade-001",
        symbol="XAUUSD",
        side=OrderSide.BUY,
        order_status=OrderStatus.FILLED,
        entry_price=Decimal("4377.97"),
        exit_price=Decimal("4372.97"),
        quantity=Decimal("0.01"),
        stop_loss=Decimal("4372.97"),
        take_profit=Decimal("4387.97"),
        gross_pnl=Decimal("-5.00"),
        commission=Decimal("-0.04"),
        swap=Decimal(0),
        net_pnl=Decimal("-5.04"),
        realized=True,
        opened_at=opened_at,
        closed_at=closed_at,
        exit_reason="stop_loss",
        maximum_adverse_excursion=Decimal("5.00"),
        maximum_favorable_excursion=Decimal("0.50"),
    )


def test_journal_records_and_retrieves_decision() -> None:
    journal = InMemoryTradeJournal()
    decision = make_decision()

    journal.record_decision(decision)

    assert journal.get_decision("decision-001") == decision


def test_journal_returns_none_for_unknown_decision() -> None:
    journal = InMemoryTradeJournal()

    assert journal.get_decision("missing") is None


def test_journal_rejects_duplicate_decision() -> None:
    journal = InMemoryTradeJournal()
    decision = make_decision()

    journal.record_decision(decision)

    with pytest.raises(
        ValueError,
        match="Decision already recorded: decision-001",
    ):
        journal.record_decision(decision)


def test_journal_records_and_retrieves_outcome() -> None:
    journal = InMemoryTradeJournal()
    outcome = make_outcome()

    journal.record_outcome(outcome)

    assert journal.get_outcome("trade-001") == outcome


def test_journal_returns_none_for_unknown_outcome() -> None:
    journal = InMemoryTradeJournal()

    assert journal.get_outcome("missing") is None


def test_journal_rejects_duplicate_outcome() -> None:
    journal = InMemoryTradeJournal()
    outcome = make_outcome()

    journal.record_outcome(outcome)

    with pytest.raises(
        ValueError,
        match="Outcome already recorded: trade-001",
    ):
        journal.record_outcome(outcome)


def test_journal_keeps_decisions_and_outcomes_independent() -> None:
    journal = InMemoryTradeJournal()
    decision = make_decision()
    outcome = make_outcome()

    journal.record_decision(decision)
    journal.record_outcome(outcome)

    assert journal.get_decision(decision.id) == decision
    assert journal.get_outcome(outcome.trade_id) == outcome