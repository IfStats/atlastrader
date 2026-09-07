from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.market_data.comparison import (
    MarketDataComparison,
    MarketDataComparisonStatus,
    SourcePriceComparison,
)
from packages.market_data.quality import (
    MarketDataQualityPolicy,
)

NOW = datetime(
    2026,
    9,
    7,
    14,
    0,
    tzinfo=UTC,
)


def make_comparison(
    status: MarketDataComparisonStatus,
    *,
    reasons: list[str] | None = None,
) -> MarketDataComparison:
    return MarketDataComparison(
        symbol="XAUUSD",
        authoritative_source="MT5",
        authoritative_price=Decimal("4378.10"),
        consensus_price=Decimal("4378.11"),
        consensus_deviation_bps=Decimal("0.02"),
        generated_at=NOW,
        source_count=3,
        fresh_source_count=3,
        status=status,
        sources=[
            SourcePriceComparison(
                source="MT5",
                price=Decimal("4378.10"),
                timestamp=NOW,
                age_seconds=0.0,
                deviation_bps=Decimal(0),
                is_authoritative=True,
                is_stale=False,
                is_deviant=False,
            )
        ],
        reasons=list(reasons or []),
    )


def test_healthy_market_data_permits_full_confidence() -> None:
    policy = MarketDataQualityPolicy()

    decision = policy.evaluate(
        make_comparison(
            MarketDataComparisonStatus.HEALTHY
        )
    )

    assert decision.trading_permitted is True
    assert decision.confidence_multiplier == 1.0

    assert (
        decision.status
        is MarketDataComparisonStatus.HEALTHY
    )

    assert decision.reasons == []


def test_degraded_market_data_reduces_confidence() -> None:
    policy = MarketDataQualityPolicy(
        degraded_confidence_multiplier=0.70,
    )

    decision = policy.evaluate(
        make_comparison(
            MarketDataComparisonStatus.DEGRADED,
            reasons=[
                "stale_reference:Twelve Data",
            ],
        )
    )

    assert decision.trading_permitted is True
    assert decision.confidence_multiplier == 0.70

    assert (
        "market_data_degraded"
        in decision.reasons
    )

    assert (
        "stale_reference:Twelve Data"
        in decision.reasons
    )


def test_degraded_market_data_can_be_blocked() -> None:
    policy = MarketDataQualityPolicy(
        block_degraded=True,
    )

    decision = policy.evaluate(
        make_comparison(
            MarketDataComparisonStatus.DEGRADED,
        )
    )

    assert decision.trading_permitted is False
    assert decision.confidence_multiplier == 0.0

    assert (
        "market_data_degraded_blocked"
        in decision.reasons
    )


def test_anomalous_market_data_blocks_trading() -> None:
    policy = MarketDataQualityPolicy()

    decision = policy.evaluate(
        make_comparison(
            MarketDataComparisonStatus.ANOMALOUS,
            reasons=[
                "reference_deviation:Massive",
            ],
        )
    )

    assert decision.trading_permitted is False
    assert decision.confidence_multiplier == 0.0

    assert (
        decision.status
        is MarketDataComparisonStatus.ANOMALOUS
    )

    assert (
        "market_data_anomalous"
        in decision.reasons
    )

    assert (
        "reference_deviation:Massive"
        in decision.reasons
    )


@pytest.mark.parametrize(
    "multiplier",
    [
        -0.01,
        1.01,
    ],
)
def test_policy_rejects_invalid_multiplier(
    multiplier: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="between 0 and 1",
    ):
        MarketDataQualityPolicy(
            degraded_confidence_multiplier=multiplier
        )


def test_zero_degraded_multiplier_is_valid() -> None:
    policy = MarketDataQualityPolicy(
        degraded_confidence_multiplier=0.0,
    )

    decision = policy.evaluate(
        make_comparison(
            MarketDataComparisonStatus.DEGRADED
        )
    )

    assert decision.trading_permitted is True
    assert decision.confidence_multiplier == 0.0