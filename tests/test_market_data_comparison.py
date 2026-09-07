from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from packages.core.models import Quote
from packages.market_data.comparison import (
    MarketDataComparator,
    MarketDataComparisonStatus,
)
from packages.market_data.observations import (
    MarketPriceObservation,
    PriceObservationType,
)

BASE_TIME = datetime(
    2026,
    9,
    7,
    10,
    0,
    tzinfo=UTC,
)


def make_quote(
    *,
    symbol: str = "XAUUSD",
    bid: str = "100.00",
    ask: str = "100.20",
    timestamp: datetime = BASE_TIME,
) -> Quote:
    return Quote(
        symbol=symbol,
        bid=Decimal(bid),
        ask=Decimal(ask),
        timestamp=timestamp,
    )


def make_observation(
    *,
    symbol: str = "XAUUSD",
    price: str = "100.10",
    source: str = "Twelve Data",
    timestamp: datetime = BASE_TIME,
) -> MarketPriceObservation:
    return MarketPriceObservation(
        symbol=symbol,
        price=Decimal(price),
        timestamp=timestamp,
        source=source,
        price_type=PriceObservationType.MID,
    )


def test_comparator_reports_healthy_consensus() -> None:
    comparator = MarketDataComparator(
        max_age_seconds=5,
        max_deviation_bps=Decimal(5),
        min_fresh_sources=2,
    )

    result = comparator.compare(
        authoritative_source="MT5",
        authoritative_quote=make_quote(),
        reference_quotes={
            "Massive": make_quote(
                bid="100.05",
                ask="100.15",
            ),
        },
        observations=[
            make_observation(
                price="100.11"
            )
        ],
        now=BASE_TIME + timedelta(seconds=1),
    )

    assert result.symbol == "XAUUSD"
    assert result.authoritative_source == "MT5"
    assert (
        result.authoritative_price
        == Decimal("100.10")
    )
    assert (
        result.consensus_price
        == Decimal("100.10")
    )
    assert result.source_count == 3
    assert result.fresh_source_count == 3

    assert (
        result.status
        is MarketDataComparisonStatus.HEALTHY
    )

    assert result.reasons == []

    assert result.sources[0].is_authoritative
    assert not result.sources[0].is_stale

    massive = result.sources[1]
    assert massive.source == "Massive"
    assert not massive.is_deviant


def test_comparator_detects_reference_deviation() -> None:
    comparator = MarketDataComparator(
        max_deviation_bps=Decimal(5),
    )

    result = comparator.compare(
        authoritative_source="MT5",
        authoritative_quote=make_quote(),
        reference_quotes={
            "Massive": make_quote(
                bid="101.00",
                ask="101.20",
            ),
        },
        observations=[
            make_observation()
        ],
        now=BASE_TIME,
    )

    assert (
        result.status
        is MarketDataComparisonStatus.ANOMALOUS
    )

    assert (
        "reference_deviation:Massive"
        in result.reasons
    )

    assert result.sources[1].is_deviant


def test_stale_reference_degrades_comparison() -> None:
    comparator = MarketDataComparator(
        max_age_seconds=5,
    )

    result = comparator.compare(
        authoritative_source="MT5",
        authoritative_quote=make_quote(),
        reference_quotes={
            "Massive": make_quote(
                timestamp=(
                    BASE_TIME
                    - timedelta(seconds=30)
                ),
            ),
        },
        observations=[
            make_observation()
        ],
        now=BASE_TIME,
    )

    assert (
        result.status
        is MarketDataComparisonStatus.DEGRADED
    )

    assert (
        "stale_reference:Massive"
        in result.reasons
    )

    assert result.sources[1].is_stale


def test_stale_authoritative_source_is_anomalous() -> None:
    comparator = MarketDataComparator(
        max_age_seconds=5,
    )

    result = comparator.compare(
        authoritative_source="MT5",
        authoritative_quote=make_quote(
            timestamp=(
                BASE_TIME
                - timedelta(seconds=30)
            ),
        ),
        observations=[
            make_observation()
        ],
        now=BASE_TIME,
    )

    assert (
        result.status
        is MarketDataComparisonStatus.ANOMALOUS
    )

    assert (
        "authoritative_source_stale"
        in result.reasons
    )


def test_insufficient_fresh_sources_is_degraded() -> None:
    comparator = MarketDataComparator(
        min_fresh_sources=2,
    )

    result = comparator.compare(
        authoritative_source="MT5",
        authoritative_quote=make_quote(),
        now=BASE_TIME,
    )

    assert (
        result.status
        is MarketDataComparisonStatus.DEGRADED
    )

    assert result.fresh_source_count == 1

    assert (
        "insufficient_fresh_sources"
        in result.reasons
    )


def test_consensus_excludes_stale_reference() -> None:
    comparator = MarketDataComparator(
        max_age_seconds=5,
        max_deviation_bps=Decimal(500),
        min_fresh_sources=2,
    )

    result = comparator.compare(
        authoritative_source="MT5",
        authoritative_quote=make_quote(
            bid="99.90",
            ask="100.10",
        ),
        reference_quotes={
            "Massive": make_quote(
                bid="999.90",
                ask="1000.10",
                timestamp=(
                    BASE_TIME
                    - timedelta(seconds=30)
                ),
            ),
        },
        observations=[
            make_observation(
                price="102.00"
            )
        ],
        now=BASE_TIME,
    )

    assert (
        result.consensus_price
        == Decimal(101)
    )

    assert result.fresh_source_count == 2

    assert (
        result.status
        is MarketDataComparisonStatus.DEGRADED
    )


def test_comparator_rejects_reference_symbol_mismatch() -> None:
    comparator = MarketDataComparator()

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        comparator.compare(
            authoritative_source="MT5",
            authoritative_quote=make_quote(),
            reference_quotes={
                "Massive": make_quote(
                    symbol="EURUSD"
                ),
            },
            now=BASE_TIME,
        )


def test_comparator_rejects_observation_symbol_mismatch() -> None:
    comparator = MarketDataComparator()

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        comparator.compare(
            authoritative_source="MT5",
            authoritative_quote=make_quote(),
            observations=[
                make_observation(
                    symbol="EURUSD"
                )
            ],
            now=BASE_TIME,
        )


def test_comparator_rejects_duplicate_source_names() -> None:
    comparator = MarketDataComparator()

    with pytest.raises(
        ValueError,
        match="Duplicate",
    ):
        comparator.compare(
            authoritative_source="MT5",
            authoritative_quote=make_quote(),
            reference_quotes={
                "Twelve Data": make_quote(),
            },
            observations=[
                make_observation(
                    source="twelve data"
                )
            ],
            now=BASE_TIME,
        )


def test_comparator_rejects_naive_comparison_time() -> None:
    comparator = MarketDataComparator()

    naive_time = BASE_TIME.replace(
        tzinfo=None
    )

    with pytest.raises(
        ValueError,
        match="comparison time",
    ):
        comparator.compare(
            authoritative_source="MT5",
            authoritative_quote=make_quote(),
            now=naive_time,
        )


def test_comparator_rejects_invalid_configuration() -> None:
    with pytest.raises(
        ValueError,
        match="max_age_seconds",
    ):
        MarketDataComparator(
            max_age_seconds=0
        )

    with pytest.raises(
        ValueError,
        match="max_deviation_bps",
    ):
        MarketDataComparator(
            max_deviation_bps=Decimal(0)
        )

    with pytest.raises(
        ValueError,
        match="min_fresh_sources",
    ):
        MarketDataComparator(
            min_fresh_sources=0
        )