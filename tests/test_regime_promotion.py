from decimal import Decimal

from packages.performance.models import (
    PerformanceSummary,
)
from packages.regime.models import (
    RegimeQuality,
    StrategyRegimePattern,
)
from packages.regime.promotion import (
    RegimePromotionEvaluator,
)


def make_performance(
    *,
    total_trades: int = 30,
    expectancy: Decimal = Decimal(2),
    profit_factor: Decimal | None = (
        Decimal("1.50")
    ),
    payoff_ratio: Decimal | None = (
        Decimal("1.40")
    ),
    win_rate: Decimal = Decimal("0.60"),
) -> PerformanceSummary:
    winning_trades = int(
        total_trades
        * float(win_rate)
    )

    losing_trades = (
        total_trades
        - winning_trades
    )

    return PerformanceSummary(
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        breakeven_trades=0,
        win_rate=win_rate,
        loss_rate=(
            Decimal(1)
            - win_rate
        ),
        breakeven_rate=Decimal(0),
        total_net_pnl=(
            expectancy
            * Decimal(total_trades)
        ),
        total_positive_net_pnl=Decimal(
            100
        ),
        total_negative_net_pnl=Decimal(
            -60
        ),
        average_net_pnl=expectancy,
        average_win=Decimal(5),
        average_loss=Decimal(-3),
        profit_factor=profit_factor,
        payoff_ratio=payoff_ratio,
        expectancy=expectancy,
    )


def make_pattern(
    *,
    sample_size: int = 30,
    quality: RegimeQuality = (
        RegimeQuality.STRONG
    ),
    expectancy: Decimal = Decimal(2),
    profit_factor: Decimal | None = (
        Decimal("1.50")
    ),
) -> StrategyRegimePattern:
    performance = make_performance(
        total_trades=sample_size,
        expectancy=expectancy,
        profit_factor=profit_factor,
    )

    return StrategyRegimePattern(
        strategy="momentum",
        regime_key=(
            "strong_uptrend|"
            "normal|"
            "aligned"
        ),
        sample_size=sample_size,
        performance=performance,
        quality=quality,
        sufficient_sample=(
            sample_size >= 10
        ),
    )


def test_supported_pattern_is_eligible() -> None:
    evaluator = (
        RegimePromotionEvaluator()
    )

    result = evaluator.evaluate(
        make_pattern()
    )

    assert result.eligible

    assert (
        result.rejection_reasons
        == []
    )


def test_small_sample_is_rejected() -> None:
    evaluator = (
        RegimePromotionEvaluator()
    )

    result = evaluator.evaluate(
        make_pattern(
            sample_size=10
        )
    )

    assert not result.eligible

    assert (
        "insufficient_sample_size"
        in result.rejection_reasons
    )


def test_negative_expectancy_is_rejected() -> None:
    evaluator = (
        RegimePromotionEvaluator()
    )

    result = evaluator.evaluate(
        make_pattern(
            expectancy=Decimal(-1),
            quality=(
                RegimeQuality.NEGATIVE
            ),
            profit_factor=Decimal(
                "0.90"
            ),
        )
    )

    assert not result.eligible

    assert (
        "non_positive_expectancy"
        in result.rejection_reasons
    )


def test_poor_quality_is_rejected() -> None:
    evaluator = (
        RegimePromotionEvaluator()
    )

    result = evaluator.evaluate(
        make_pattern(
            quality=RegimeQuality.POOR,
        )
    )

    assert not result.eligible

    assert (
        "unsupported_quality"
        in result.rejection_reasons
    )


def test_low_profit_factor_is_rejected() -> None:
    evaluator = (
        RegimePromotionEvaluator()
    )

    result = evaluator.evaluate(
        make_pattern(
            profit_factor=Decimal(
                "1.10"
            )
        )
    )

    assert not result.eligible

    assert (
        "profit_factor_below_threshold"
        in result.rejection_reasons
    )


def test_missing_profit_factor_is_rejected() -> None:
    evaluator = (
        RegimePromotionEvaluator()
    )

    result = evaluator.evaluate(
        make_pattern(
            profit_factor=None
        )
    )

    assert not result.eligible

    assert (
        "missing_profit_factor"
        in result.rejection_reasons
    )


def test_threshold_sample_size_is_eligible() -> None:
    evaluator = (
        RegimePromotionEvaluator()
    )

    result = evaluator.evaluate(
        make_pattern(
            sample_size=30
        )
    )

    assert result.eligible


def test_threshold_profit_factor_is_eligible() -> None:
    evaluator = (
        RegimePromotionEvaluator()
    )

    result = evaluator.evaluate(
        make_pattern(
            profit_factor=Decimal(
                "1.20"
            )
        )
    )

    assert result.eligible


def test_pattern_identity_is_preserved() -> None:
    evaluator = (
        RegimePromotionEvaluator()
    )

    pattern = make_pattern()

    result = evaluator.evaluate(
        pattern
    )

    assert (
        result.pattern_key
        == pattern.key
    )