from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from packages.core.enums import (
    OrderSide,
    OrderStatus,
    SignalDirection,
    StrategyType,
    Timeframe,
)
from packages.core.trading_journal import TradeDecision, TradeOutcome


@pytest.fixture
def decision_data() -> dict[str, object]:
    timestamp = datetime(2026, 9, 3, 10, 0, 0, tzinfo=UTC)

    return {
        "id": "decision-001",
        "symbol": "XAUUSD",
        "direction": SignalDirection.LONG,
        "strategy": StrategyType.MOMENTUM,
        "timeframe": Timeframe.M5,
        "decision": SignalDirection.LONG,
        "status": "approved",
        "timestamp": timestamp,
        "signal_score": 82.5,
        "confidence": 0.82,
        "entry_price": Decimal("4377.97"),
        "stop_loss": Decimal("4372.97"),
        "take_profit": Decimal("4387.97"),
        "risk_reward_ratio": Decimal("2.0"),
        "requested_quantity": Decimal("0.01"),
        "risk_amount": Decimal("5.00"),
        "risk_percentage": Decimal("0.0027"),
        "rationale": [
            "Bullish momentum confirmed",
            "Spread within configured limit",
        ],
        "rejection_reasons": [],
        "market_state": {
            "trend_score": 0.75,
            "momentum_score": 0.82,
            "volatility_score": 0.55,
        },
        "order_id": "order-001",
        "created_at": timestamp,
        "updated_at": timestamp,
    }


@pytest.fixture
def outcome_data() -> dict[str, object]:
    opened_at = datetime(2026, 9, 3, 10, 0, 0, tzinfo=UTC)
    closed_at = opened_at + timedelta(minutes=15)

    return {
        "trade_id": "trade-001",
        "symbol": "XAUUSD",
        "side": OrderSide.BUY,
        "order_status": OrderStatus.FILLED,
        "entry_price": Decimal("4377.97"),
        "exit_price": Decimal("4372.97"),
        "quantity": Decimal("0.01"),
        "stop_loss": Decimal("4372.97"),
        "take_profit": Decimal("4387.97"),
        "gross_pnl": Decimal("-5.00"),
        "commission": Decimal("-0.04"),
        "swap": Decimal(0),
        "net_pnl": Decimal("-5.04"),
        "realized": True,
        "opened_at": opened_at,
        "closed_at": closed_at,
        "exit_reason": "stop_loss",
        "maximum_adverse_excursion": Decimal("5.00"),
        "maximum_favorable_excursion": Decimal("0.50"),
    }


def test_trade_decision_accepts_valid_data(
    decision_data: dict[str, object],
) -> None:
    decision = TradeDecision.model_validate(decision_data)

    assert decision.id == "decision-001"
    assert decision.symbol == "XAUUSD"
    assert decision.decision == SignalDirection.LONG
    assert decision.confidence == 0.82
    assert decision.entry_price == Decimal("4377.97")


def test_trade_decision_is_immutable(
    decision_data: dict[str, object],
) -> None:
    decision = TradeDecision.model_validate(decision_data)

    with pytest.raises(ValidationError):
        decision.symbol = "EURUSD"


def test_flat_decision_cannot_have_order_id(
    decision_data: dict[str, object],
) -> None:
    decision_data["decision"] = SignalDirection.FLAT
    decision_data["direction"] = SignalDirection.FLAT
    decision_data["order_id"] = "order-001"

    with pytest.raises(ValidationError, match="FLAT decisions"):
        TradeDecision.model_validate(decision_data)


def test_directional_decision_requires_entry_price(
    decision_data: dict[str, object],
) -> None:
    decision_data["entry_price"] = None

    with pytest.raises(
        ValidationError,
        match="Directional decisions require an entry_price",
    ):
        TradeDecision.model_validate(decision_data)


def test_trade_decision_signal_score_rejects_value_above_100(
    decision_data: dict[str, object],
) -> None:
    decision_data["signal_score"] = 100.1

    with pytest.raises(ValidationError):
        TradeDecision.model_validate(decision_data)


def test_trade_decision_confidence_rejects_value_above_1(
    decision_data: dict[str, object],
) -> None:
    decision_data["confidence"] = 1.01

    with pytest.raises(ValidationError):
        TradeDecision.model_validate(decision_data)


def test_trade_outcome_accepts_valid_realized_trade(
    outcome_data: dict[str, object],
) -> None:
    outcome = TradeOutcome.model_validate(outcome_data)

    assert outcome.trade_id == "trade-001"
    assert outcome.symbol == "XAUUSD"
    assert outcome.realized is True
    assert outcome.exit_price == Decimal("4372.97")
    assert outcome.net_pnl == Decimal("-5.04")


def test_realized_trade_requires_exit_price(
    outcome_data: dict[str, object],
) -> None:
    outcome_data["exit_price"] = None

    with pytest.raises(
        ValidationError,
        match="Realized trades require an exit_price",
    ):
        TradeOutcome.model_validate(outcome_data)


def test_realized_trade_requires_closed_at(
    outcome_data: dict[str, object],
) -> None:
    outcome_data["closed_at"] = None

    with pytest.raises(
        ValidationError,
        match="Realized trades require closed_at",
    ):
        TradeOutcome.model_validate(outcome_data)


def test_closed_at_must_be_later_than_opened_at(
    outcome_data: dict[str, object],
) -> None:
    opened_at = outcome_data["opened_at"]
    assert isinstance(opened_at, datetime)

    outcome_data["closed_at"] = opened_at - timedelta(minutes=1)

    with pytest.raises(
        ValidationError,
        match="closed_at must be later than opened_at",
    ):
        TradeOutcome.model_validate(outcome_data)


def test_closed_at_cannot_equal_opened_at(
    outcome_data: dict[str, object],
) -> None:
    opened_at = outcome_data["opened_at"]
    assert isinstance(opened_at, datetime)

    outcome_data["closed_at"] = opened_at

    with pytest.raises(
        ValidationError,
        match="closed_at must be later than opened_at",
    ):
        TradeOutcome.model_validate(outcome_data)


def test_unrealized_trade_can_have_no_exit(
    outcome_data: dict[str, object],
) -> None:
    outcome_data["realized"] = False
    outcome_data["exit_price"] = None
    outcome_data["closed_at"] = None

    outcome = TradeOutcome.model_validate(outcome_data)

    assert outcome.realized is False
    assert outcome.exit_price is None
    assert outcome.closed_at is None


def test_trade_outcome_preserves_decimal_precision(
    outcome_data: dict[str, object],
) -> None:
    outcome = TradeOutcome.model_validate(outcome_data)

    assert isinstance(outcome.entry_price, Decimal)
    assert isinstance(outcome.exit_price, Decimal)
    assert isinstance(outcome.gross_pnl, Decimal)
    assert isinstance(outcome.net_pnl, Decimal)


def test_trade_decision_serializes_market_state(
    decision_data: dict[str, object],
) -> None:
    decision = TradeDecision.model_validate(decision_data)

    assert decision.market_state["trend_score"] == 0.75
    assert decision.market_state["momentum_score"] == 0.82
    assert decision.market_state["volatility_score"] == 0.55


def test_trade_decision_defaults(
    decision_data: dict[str, object],
) -> None:
    decision_data["decision"] = SignalDirection.FLAT
    decision_data["direction"] = SignalDirection.FLAT

    decision_data.pop("entry_price")
    decision_data.pop("stop_loss")
    decision_data.pop("take_profit")
    decision_data.pop("risk_reward_ratio")
    decision_data.pop("requested_quantity")
    decision_data.pop("risk_amount")
    decision_data.pop("risk_percentage")
    decision_data.pop("order_id")
    decision_data.pop("rationale")
    decision_data.pop("rejection_reasons")
    decision_data.pop("market_state")

    decision = TradeDecision.model_validate(decision_data)

    assert decision.entry_price is None
    assert decision.stop_loss is None
    assert decision.take_profit is None
    assert decision.risk_reward_ratio is None
    assert decision.requested_quantity is None
    assert decision.risk_amount is None
    assert decision.risk_percentage is None
    assert decision.order_id is None
    assert decision.rationale == []
    assert decision.rejection_reasons == []
    assert decision.market_state == {}