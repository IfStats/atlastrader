from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.core.enums import (
    OrderSide,
    OrderStatus,
    SignalDirection,
    StrategyType,
    Timeframe,
)
from packages.core.trading_journal import (
    TradeDecision,
    TradeOutcome,
)
from packages.learning.dataset import (
    LearningDatasetAssembler,
)

BASE_TIME = datetime(
    2026,
    9,
    7,
    10,
    0,
    tzinfo=UTC,
)


def make_decision(
    *,
    decision_id: str,
    broker_order_id: str | None,
    symbol: str = "XAUUSD",
    minute: int = 0,
) -> TradeDecision:
    timestamp = BASE_TIME.replace(
        minute=minute
    )

    return TradeDecision(
        id=decision_id,
        symbol=symbol,
        direction=SignalDirection.LONG,
        strategy=StrategyType.MOMENTUM,
        timeframe=Timeframe.M5,
        decision=SignalDirection.LONG,
        status="approved",
        timestamp=timestamp,
        signal_score=85.0,
        confidence=0.85,
        entry_price=Decimal("4377.97"),
        stop_loss=Decimal("4372.97"),
        take_profit=Decimal("4387.97"),
        risk_reward_ratio=Decimal(2),
        requested_quantity=Decimal("0.01"),
        market_state={
            "price": "4377.97",
            "trend_score": 0.8,
            "momentum_score": 0.9,
            "volatility_score": 0.4,
            "volatility": "5",
            "spread": "0.20",
            "market_status": "open",
            "session": "london",
            "is_tradeable": True,
        },
        order_id=f"atlas-{decision_id}",
        broker_order_id=broker_order_id,
        created_at=timestamp,
        updated_at=timestamp,
    )


def make_outcome(
    *,
    trade_id: str,
    broker_order_ids: list[str],
    symbol: str = "XAUUSD",
    minute: int = 0,
) -> TradeOutcome:
    opened_at = BASE_TIME.replace(
        minute=minute + 1
    )

    closed_at = BASE_TIME.replace(
        minute=minute + 5
    )

    return TradeOutcome(
        trade_id=trade_id,
        symbol=symbol,
        side=OrderSide.BUY,
        order_status=OrderStatus.FILLED,
        entry_price=Decimal("4378.10"),
        exit_price=Decimal("4388.10"),
        quantity=Decimal("0.01"),
        gross_pnl=Decimal(10),
        commission=Decimal("-0.04"),
        swap=Decimal(0),
        net_pnl=Decimal("9.96"),
        realized=True,
        opened_at=opened_at,
        closed_at=closed_at,
        exit_reason="take_profit",
        entry_broker_order_ids=(
            broker_order_ids
        ),
    )


def test_assembles_exact_unique_matches() -> None:
    assembler = LearningDatasetAssembler()

    result = assembler.assemble(
        decisions=[
            make_decision(
                decision_id="decision-2",
                broker_order_id="broker-2",
                minute=2,
            ),
            make_decision(
                decision_id="decision-1",
                broker_order_id="broker-1",
                minute=0,
            ),
        ],
        outcomes=[
            make_outcome(
                trade_id="trade-1",
                broker_order_ids=[
                    "broker-1"
                ],
                minute=0,
            ),
            make_outcome(
                trade_id="trade-2",
                broker_order_ids=[
                    "broker-2"
                ],
                minute=2,
            ),
        ],
    )

    assert [
        record.decision_id
        for record in result.records
    ] == [
        "decision-1",
        "decision-2",
    ]

    assert (
        result.unmatched_decision_ids
        == []
    )
    assert result.unmatched_trade_ids == []
    assert (
        result.ambiguous_broker_order_ids
        == []
    )
    assert (
        result.unsupported_trade_ids
        == []
    )


def test_reports_unmatched_decision() -> None:
    assembler = LearningDatasetAssembler()

    result = assembler.assemble(
        decisions=[
            make_decision(
                decision_id="decision-1",
                broker_order_id="broker-1",
            )
        ],
        outcomes=[],
    )

    assert result.records == []

    assert result.unmatched_decision_ids == [
        "decision-1"
    ]


def test_reports_unmatched_outcome() -> None:
    assembler = LearningDatasetAssembler()

    result = assembler.assemble(
        decisions=[],
        outcomes=[
            make_outcome(
                trade_id="trade-1",
                broker_order_ids=[
                    "broker-1"
                ],
            )
        ],
    )

    assert result.records == []

    assert result.unmatched_trade_ids == [
        "trade-1"
    ]


def test_reports_duplicate_decision_lineage_as_ambiguous() -> None:
    assembler = LearningDatasetAssembler()

    result = assembler.assemble(
        decisions=[
            make_decision(
                decision_id="decision-1",
                broker_order_id="broker-1",
            ),
            make_decision(
                decision_id="decision-2",
                broker_order_id="broker-1",
                minute=1,
            ),
        ],
        outcomes=[
            make_outcome(
                trade_id="trade-1",
                broker_order_ids=[
                    "broker-1"
                ],
            )
        ],
    )

    assert result.records == []

    assert (
        result.ambiguous_broker_order_ids
        == ["broker-1"]
    )


def test_reports_duplicate_outcome_lineage_as_ambiguous() -> None:
    assembler = LearningDatasetAssembler()

    result = assembler.assemble(
        decisions=[
            make_decision(
                decision_id="decision-1",
                broker_order_id="broker-1",
            )
        ],
        outcomes=[
            make_outcome(
                trade_id="trade-1",
                broker_order_ids=[
                    "broker-1"
                ],
            ),
            make_outcome(
                trade_id="trade-2",
                broker_order_ids=[
                    "broker-1"
                ],
                minute=2,
            ),
        ],
    )

    assert result.records == []

    assert (
        result.ambiguous_broker_order_ids
        == ["broker-1"]
    )


def test_reports_multi_entry_trade_as_unsupported() -> None:
    assembler = LearningDatasetAssembler()

    result = assembler.assemble(
        decisions=[
            make_decision(
                decision_id="decision-1",
                broker_order_id="broker-1",
            ),
            make_decision(
                decision_id="decision-2",
                broker_order_id="broker-2",
                minute=1,
            ),
        ],
        outcomes=[
            make_outcome(
                trade_id="trade-1",
                broker_order_ids=[
                    "broker-1",
                    "broker-2",
                ],
            )
        ],
    )

    assert result.records == []

    assert result.unsupported_trade_ids == [
        "trade-1"
    ]

    assert (
        result.ambiguous_broker_order_ids
        == [
            "broker-1",
            "broker-2",
        ]
    )


def test_matched_corrupt_pair_is_not_silently_ignored() -> None:
    assembler = LearningDatasetAssembler()

    with pytest.raises(
        ValueError,
        match="symbols do not match",
    ):
        assembler.assemble(
            decisions=[
                make_decision(
                    decision_id="decision-1",
                    broker_order_id="broker-1",
                )
            ],
            outcomes=[
                make_outcome(
                    trade_id="trade-1",
                    broker_order_ids=[
                        "broker-1"
                    ],
                    symbol="EURUSD",
                )
            ],
        )


def test_rejects_duplicate_decision_ids() -> None:
    assembler = LearningDatasetAssembler()

    decision = make_decision(
        decision_id="decision-1",
        broker_order_id="broker-1",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate trade decision IDs",
    ):
        assembler.assemble(
            decisions=[
                decision,
                decision,
            ],
            outcomes=[],
        )


def test_rejects_duplicate_trade_ids() -> None:
    assembler = LearningDatasetAssembler()

    outcome = make_outcome(
        trade_id="trade-1",
        broker_order_ids=[
            "broker-1"
        ],
    )

    with pytest.raises(
        ValueError,
        match="Duplicate trade outcome IDs",
    ):
        assembler.assemble(
            decisions=[],
            outcomes=[
                outcome,
                outcome,
            ],
        )