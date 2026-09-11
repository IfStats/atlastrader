from datetime import UTC, datetime
from decimal import Decimal

from packages.candidate.generator import CandidateStrategyGenerator
from packages.candidate.models import CandidateStrategyStatus
from packages.performance.models import PerformanceSummary
from packages.regime.models import RegimeQuality, StrategyRegimePattern

NOW = datetime(2026, 9, 11, 13, 0, tzinfo=UTC)


def make_performance(
    *,
    total_trades: int = 30,
    expectancy: Decimal = Decimal(2),
    profit_factor: Decimal | None = Decimal("1.50"),
) -> PerformanceSummary:
    winning_trades = (total_trades * 3) // 5
    losing_trades = total_trades - winning_trades

    return PerformanceSummary(
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        breakeven_trades=0,
        win_rate=Decimal("0.60"),
        loss_rate=Decimal("0.40"),
        breakeven_rate=Decimal(0),
        total_net_pnl=expectancy * Decimal(total_trades),
        total_positive_net_pnl=Decimal(100),
        total_negative_net_pnl=Decimal(-60),
        average_net_pnl=expectancy,
        average_win=Decimal(5),
        average_loss=Decimal(-3),
        profit_factor=profit_factor,
        payoff_ratio=Decimal("1.40"),
        expectancy=expectancy,
    )


def make_pattern(
    *,
    strategy: str = "momentum",
    regime_key: str = "strong_uptrend|normal|aligned",
    sample_size: int = 30,
    quality: RegimeQuality = RegimeQuality.STRONG,
    expectancy: Decimal = Decimal(2),
    profit_factor: Decimal | None = Decimal("1.50"),
) -> StrategyRegimePattern:
    return StrategyRegimePattern(
        strategy=strategy,
        regime_key=regime_key,
        sample_size=sample_size,
        performance=make_performance(
            total_trades=sample_size,
            expectancy=expectancy,
            profit_factor=profit_factor,
        ),
        quality=quality,
        sufficient_sample=(sample_size >= 10),
    )


def test_eligible_pattern_generates_validation_candidate() -> None:
    candidate = CandidateStrategyGenerator().generate(make_pattern(), created_at=NOW)
    assert candidate.status is CandidateStrategyStatus.ELIGIBLE_FOR_VALIDATION


def test_small_sample_generates_rejected_candidate() -> None:
    candidate = CandidateStrategyGenerator().generate(
        make_pattern(sample_size=10),
        created_at=NOW,
    )
    assert candidate.status is CandidateStrategyStatus.REJECTED
    assert "insufficient_sample_size" in candidate.rationale


def test_negative_pattern_generates_rejected_candidate() -> None:
    candidate = CandidateStrategyGenerator().generate(
        make_pattern(
            expectancy=Decimal(-1),
            profit_factor=Decimal("0.80"),
            quality=RegimeQuality.NEGATIVE,
        ),
        created_at=NOW,
    )
    assert candidate.status is CandidateStrategyStatus.REJECTED


def test_candidate_preserves_pattern_identity() -> None:
    pattern = make_pattern()
    candidate = CandidateStrategyGenerator().generate(pattern, created_at=NOW)
    assert candidate.source_pattern_key == pattern.key
    assert candidate.strategy == pattern.strategy
    assert candidate.regime_key == pattern.regime_key


def test_candidate_preserves_performance_evidence() -> None:
    pattern = make_pattern()
    candidate = CandidateStrategyGenerator().generate(pattern, created_at=NOW)
    assert candidate.sample_size == pattern.sample_size
    assert candidate.expectancy == pattern.performance.expectancy
    assert candidate.win_rate == pattern.performance.win_rate
    assert candidate.profit_factor == pattern.performance.profit_factor
    assert candidate.payoff_ratio == pattern.performance.payoff_ratio


def test_same_pattern_generates_same_candidate_id() -> None:
    generator = CandidateStrategyGenerator()
    pattern = make_pattern()
    first = generator.generate(pattern, created_at=NOW)
    second = generator.generate(pattern, created_at=NOW)
    assert first.id == second.id


def test_different_patterns_generate_different_candidate_ids() -> None:
    generator = CandidateStrategyGenerator()
    first = generator.generate(make_pattern(), created_at=NOW)
    second = generator.generate(
        make_pattern(regime_key="neutral|low|weak"),
        created_at=NOW,
    )
    assert first.id != second.id


def test_generation_does_not_mutate_source_pattern() -> None:
    generator = CandidateStrategyGenerator()
    pattern = make_pattern()
    original = pattern.model_dump()
    generator.generate(pattern, created_at=NOW)
    assert pattern.model_dump() == original
