from datetime import UTC, datetime
from decimal import Decimal

from packages.core.enums import (
    OrderSide,
    SignalDirection,
    StrategyType,
    Timeframe,
)
from packages.learning.models import (
    LearningRecord,
)
from packages.regime.models import (
    RegimeQuality,
)
from packages.regime.strategy_analysis import (
    StrategyRegimeAnalyzer,
)

NOW = datetime(
    2026,
    9,
    11,
    12,
    0,
    tzinfo=UTC,
)


def make_record(
    *,
    decision_id: str,
    net_pnl: Decimal,
    strategy: StrategyType = (
        StrategyType.MOMENTUM
    ),
    direction: SignalDirection = (
        SignalDirection.LONG
    ),
    trend_score: float = 0.8,
    momentum_score: float = 0.8,
    volatility_score: float = 0.5,
) -> LearningRecord:
    side = (
        OrderSide.BUY
        if direction
        is SignalDirection.LONG
        else OrderSide.SELL
    )

    return LearningRecord(
        decision_id=decision_id,
        trade_id=f"trade-{decision_id}",
        atlas_order_id=(
            f"atlas-{decision_id}"
        ),
        broker_order_id=(
            f"broker-{decision_id}"
        ),
        symbol="XAUUSD",
        strategy=strategy,
        timeframe=Timeframe.M5,
        direction=direction,
        side=side,
        decision_timestamp=NOW,
        opened_at=NOW,
        closed_at=NOW.replace(
            minute=10
        ),
        signal_score=85.0,
        confidence=0.85,
        requested_quantity=Decimal(
            "0.01"
        ),
        planned_entry_price=Decimal(
            "4377.97"
        ),
        executed_entry_price=Decimal(
            "4378.10"
        ),
        exit_price=Decimal(
            "4388.10"
        ),
        stop_loss=Decimal(
            "4372.97"
        ),
        take_profit=Decimal(
            "4387.97"
        ),
        risk_reward_ratio=Decimal(2),
        planned_risk_amount=Decimal(
            "5.00"
        ),
        planned_risk_percentage=Decimal(
            "0.0027"
        ),
        market_state_price=Decimal(
            "4377.97"
        ),
        trend_score=trend_score,
        momentum_score=momentum_score,
        volatility_score=volatility_score,
        volatility=Decimal(5),
        spread=Decimal(
            "0.20"
        ),
        market_status="open",
        session="london",
        is_tradeable=True,
        gross_pnl=net_pnl,
        commission=Decimal(0),
        swap=Decimal(0),
        net_pnl=net_pnl,
        profitable=(
            net_pnl > Decimal(0)
        ),
    )


def make_supported_group(
    *,
    prefix: str,
    strategy: StrategyType,
    pnl: Decimal,
    trend_score: float = 0.8,
    momentum_score: float = 0.8,
    volatility_score: float = 0.5,
) -> list[LearningRecord]:
    return [
        make_record(
            decision_id=f"{prefix}-{index}",
            net_pnl=pnl,
            strategy=strategy,
            trend_score=trend_score,
            momentum_score=momentum_score,
            volatility_score=(
                volatility_score
            ),
        )
        for index in range(10)
    ]


def test_same_strategy_same_regime_is_one_group() -> None:
    analyzer = StrategyRegimeAnalyzer()

    patterns = analyzer.analyze(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(10),
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(-5),
            ),
        ]
    )

    assert len(patterns) == 1

    assert (
        patterns[0].sample_size
        == 2
    )


def test_same_strategy_different_regimes_are_separate() -> None:
    analyzer = StrategyRegimeAnalyzer()

    patterns = analyzer.analyze(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(10),
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(-5),
                trend_score=0.0,
                momentum_score=0.0,
                volatility_score=0.1,
            ),
        ]
    )

    assert len(patterns) == 2


def test_different_strategies_same_regime_are_separate() -> None:
    analyzer = StrategyRegimeAnalyzer()

    patterns = analyzer.analyze(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(10),
                strategy=(
                    StrategyType.MOMENTUM
                ),
            ),
            make_record(
                decision_id="2",
                net_pnl=Decimal(8),
                strategy=(
                    StrategyType.MEAN_REVERSION
                ),
            ),
        ]
    )

    assert len(patterns) == 2

    assert {
        pattern.strategy
        for pattern in patterns
    } == {
        "momentum",
        "mean_reversion",
    }


def test_small_sample_is_inconclusive() -> None:
    analyzer = StrategyRegimeAnalyzer()

    patterns = analyzer.analyze(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(100),
            )
        ]
    )

    assert (
        patterns[0].quality
        is RegimeQuality.INCONCLUSIVE
    )

    assert not (
        patterns[0].sufficient_sample
    )


def test_supported_profitable_combination_is_positive() -> None:
    analyzer = StrategyRegimeAnalyzer()

    records = []

    for index in range(7):
        records.append(
            make_record(
                decision_id=f"win-{index}",
                net_pnl=Decimal(2),
            )
        )

    for index in range(3):
        records.append(
            make_record(
                decision_id=f"loss-{index}",
                net_pnl=Decimal(-1),
            )
        )

    patterns = analyzer.analyze(
        records
    )

    assert (
        patterns[0].sufficient_sample
    )

    assert (
        patterns[0].quality
        in {
            RegimeQuality.POSITIVE,
            RegimeQuality.STRONG,
        }
    )


def test_supported_losing_combination_is_poor() -> None:
    analyzer = StrategyRegimeAnalyzer()

    records = []

    for index in range(2):
        records.append(
            make_record(
                decision_id=f"win-{index}",
                net_pnl=Decimal(1),
            )
        )

    for index in range(8):
        records.append(
            make_record(
                decision_id=f"loss-{index}",
                net_pnl=Decimal(-2),
            )
        )

    patterns = analyzer.analyze(
        records
    )

    assert (
        patterns[0].sufficient_sample
    )

    assert (
        patterns[0].quality
        is RegimeQuality.POOR
    )


def test_all_records_are_partitioned() -> None:
    analyzer = StrategyRegimeAnalyzer()

    records = [
        make_record(
            decision_id="1",
            net_pnl=Decimal(10),
        ),
        make_record(
            decision_id="2",
            net_pnl=Decimal(-5),
            strategy=(
                StrategyType.MEAN_REVERSION
            ),
        ),
        make_record(
            decision_id="3",
            net_pnl=Decimal(4),
            trend_score=0.0,
            momentum_score=0.0,
            volatility_score=0.1,
        ),
    ]

    patterns = analyzer.analyze(
        records
    )

    total = sum(
        pattern.sample_size
        for pattern in patterns
    )

    assert total == len(records)


def test_pattern_key_is_deterministic() -> None:
    analyzer = StrategyRegimeAnalyzer()

    patterns = analyzer.analyze(
        [
            make_record(
                decision_id="1",
                net_pnl=Decimal(10),
            )
        ]
    )

    assert (
        patterns[0].key
        == (
            "momentum|"
            "strong_uptrend|"
            "normal|"
            "aligned"
        )
    )


def test_supported_patterns_rank_above_small_samples() -> None:
    analyzer = StrategyRegimeAnalyzer()

    supported = make_supported_group(
        prefix="supported",
        strategy=(
            StrategyType.MOMENTUM
        ),
        pnl=Decimal(1),
    )

    small_sample = [
        make_record(
            decision_id="small",
            net_pnl=Decimal(100),
            strategy=(
                StrategyType.MEAN_REVERSION
            ),
        )
    ]

    patterns = analyzer.analyze(
        supported + small_sample
    )

    assert (
        patterns[0].sufficient_sample
    )


def test_empty_dataset_returns_no_patterns() -> None:
    analyzer = StrategyRegimeAnalyzer()

    assert analyzer.analyze([]) == []