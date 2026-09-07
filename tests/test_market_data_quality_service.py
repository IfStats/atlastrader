from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from packages.core.models import Quote
from packages.market_data.base import (
    MarketDataProvider,
)
from packages.market_data.comparison import (
    MarketDataComparator,
    MarketDataComparisonStatus,
)
from packages.market_data.observations import (
    MarketPriceObservation,
    ObservationalMarketDataProvider,
    PriceObservationType,
)
from packages.market_data.quality import (
    MarketDataQualityPolicy,
)
from packages.market_data.quality_service import (
    MarketDataQualityService,
)

NOW = datetime(
    2026,
    9,
    7,
    14,
    30,
    tzinfo=UTC,
)


def make_quote(
    *,
    bid: str = "100.00",
    ask: str = "100.20",
    timestamp: datetime = NOW,
) -> Quote:
    return Quote(
        symbol="XAUUSD",
        bid=Decimal(bid),
        ask=Decimal(ask),
        timestamp=timestamp,
    )


def make_observation(
    *,
    price: str = "100.10",
    source: str = "Twelve Data",
) -> MarketPriceObservation:
    return MarketPriceObservation(
        symbol="XAUUSD",
        price=Decimal(price),
        timestamp=NOW,
        source=source,
        price_type=PriceObservationType.MID,
    )


def make_authoritative_provider() -> AsyncMock:
    provider = AsyncMock(
        spec=MarketDataProvider
    )

    provider.get_quote.return_value = (
        make_quote()
    )

    return provider


def make_quote_provider() -> AsyncMock:
    provider = AsyncMock(
        spec=MarketDataProvider
    )

    provider.get_quote.return_value = (
        make_quote(
            bid="100.05",
            ask="100.15",
        )
    )

    return provider


def make_observational_provider() -> AsyncMock:
    provider = AsyncMock(
        spec=ObservationalMarketDataProvider
    )

    provider.get_observation.return_value = (
        make_observation(
            price="100.11"
        )
    )

    return provider


@pytest.mark.asyncio
async def test_builds_healthy_quality_decision() -> None:
    mt5 = make_authoritative_provider()
    massive = make_quote_provider()
    twelve_data = (
        make_observational_provider()
    )

    service = MarketDataQualityService(
        authoritative_source="MT5",
        authoritative_provider=mt5,
        reference_quote_providers={
            "Massive": massive,
        },
        observational_providers={
            "Twelve Data": twelve_data,
        },
    )

    decision = (
        await service.get_quality_decision(
            " xauusd ",
            now=NOW,
        )
    )

    mt5.get_quote.assert_awaited_once_with(
        "XAUUSD"
    )

    massive.get_quote.assert_awaited_once_with(
        "XAUUSD"
    )

    twelve_data.get_observation.assert_awaited_once_with(
        "XAUUSD"
    )

    assert (
        decision.status
        is MarketDataComparisonStatus.HEALTHY
    )

    assert decision.trading_permitted is True
    assert decision.confidence_multiplier == 1.0
    assert decision.reasons == []


@pytest.mark.asyncio
async def test_quote_reference_failure_degrades_quality() -> None:
    mt5 = make_authoritative_provider()
    massive = make_quote_provider()
    twelve_data = (
        make_observational_provider()
    )

    massive.get_quote.side_effect = (
        RuntimeError("provider unavailable")
    )

    service = MarketDataQualityService(
        authoritative_source="MT5",
        authoritative_provider=mt5,
        reference_quote_providers={
            "Massive": massive,
        },
        observational_providers={
            "Twelve Data": twelve_data,
        },
    )

    decision = (
        await service.get_quality_decision(
            "XAUUSD",
            now=NOW,
        )
    )

    assert (
        decision.status
        is MarketDataComparisonStatus.DEGRADED
    )

    assert decision.trading_permitted is True
    assert decision.confidence_multiplier == 0.75

    assert (
        "reference_unavailable:Massive"
        in decision.reasons
    )


@pytest.mark.asyncio
async def test_observation_failure_degrades_quality() -> None:
    mt5 = make_authoritative_provider()
    massive = make_quote_provider()
    twelve_data = (
        make_observational_provider()
    )

    twelve_data.get_observation.side_effect = (
        RuntimeError("provider unavailable")
    )

    service = MarketDataQualityService(
        authoritative_source="MT5",
        authoritative_provider=mt5,
        reference_quote_providers={
            "Massive": massive,
        },
        observational_providers={
            "Twelve Data": twelve_data,
        },
    )

    decision = (
        await service.get_quality_decision(
            "XAUUSD",
            now=NOW,
        )
    )

    assert (
        decision.status
        is MarketDataComparisonStatus.DEGRADED
    )

    assert (
        "reference_unavailable:Twelve Data"
        in decision.reasons
    )


@pytest.mark.asyncio
async def test_reference_deviation_is_anomalous() -> None:
    mt5 = make_authoritative_provider()
    massive = make_quote_provider()
    twelve_data = (
        make_observational_provider()
    )

    massive.get_quote.return_value = (
        make_quote(
            bid="101.00",
            ask="101.20",
        )
    )

    service = MarketDataQualityService(
        authoritative_source="MT5",
        authoritative_provider=mt5,
        reference_quote_providers={
            "Massive": massive,
        },
        observational_providers={
            "Twelve Data": twelve_data,
        },
        comparator=MarketDataComparator(
            max_deviation_bps=Decimal(5),
        ),
    )

    decision = (
        await service.get_quality_decision(
            "XAUUSD",
            now=NOW,
        )
    )

    assert (
        decision.status
        is MarketDataComparisonStatus.ANOMALOUS
    )

    assert decision.trading_permitted is False
    assert decision.confidence_multiplier == 0.0

    assert (
        "reference_deviation:Massive"
        in decision.reasons
    )


@pytest.mark.asyncio
async def test_authoritative_failure_propagates() -> None:
    mt5 = make_authoritative_provider()
    massive = make_quote_provider()

    mt5.get_quote.side_effect = (
        RuntimeError("MT5 unavailable")
    )

    service = MarketDataQualityService(
        authoritative_source="MT5",
        authoritative_provider=mt5,
        reference_quote_providers={
            "Massive": massive,
        },
    )

    with pytest.raises(
        RuntimeError,
        match="MT5 unavailable",
    ):
        await service.get_quality_decision(
            "XAUUSD",
            now=NOW,
        )

    massive.get_quote.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_reference_sources_is_degraded() -> None:
    mt5 = make_authoritative_provider()

    service = MarketDataQualityService(
        authoritative_source="MT5",
        authoritative_provider=mt5,
    )

    decision = (
        await service.get_quality_decision(
            "XAUUSD",
            now=NOW,
        )
    )

    assert (
        decision.status
        is MarketDataComparisonStatus.DEGRADED
    )

    assert (
        "insufficient_fresh_sources"
        in decision.reasons
    )


def test_rejects_duplicate_configured_sources() -> None:
    mt5 = make_authoritative_provider()
    massive = make_quote_provider()

    with pytest.raises(
        ValueError,
        match="Duplicate market-data source",
    ):
        MarketDataQualityService(
            authoritative_source="MT5",
            authoritative_provider=mt5,
            reference_quote_providers={
                "mt5": massive,
            },
        )


@pytest.mark.asyncio
async def test_rejects_observational_source_identity_mismatch() -> None:
    mt5 = make_authoritative_provider()
    twelve_data = (
        make_observational_provider()
    )

    twelve_data.get_observation.return_value = (
        make_observation(
            source="Unexpected Provider"
        )
    )

    service = MarketDataQualityService(
        authoritative_source="MT5",
        authoritative_provider=mt5,
        observational_providers={
            "Twelve Data": twelve_data,
        },
        policy=MarketDataQualityPolicy(),
    )

    with pytest.raises(
        ValueError,
        match="does not match configured source",
    ):
        await service.get_quality_decision(
            "XAUUSD",
            now=NOW,
        )


@pytest.mark.asyncio
async def test_rejects_empty_symbol() -> None:
    mt5 = make_authoritative_provider()

    service = MarketDataQualityService(
        authoritative_source="MT5",
        authoritative_provider=mt5,
    )

    with pytest.raises(
        ValueError,
        match="symbol must not be empty",
    ):
        await service.get_quality_decision(
            "   ",
            now=NOW,
        )

    mt5.get_quote.assert_not_awaited()