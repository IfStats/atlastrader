from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from packages.market_data.observations import (
    MarketPriceObservation,
    ObservationalMarketDataProvider,
    PriceObservationType,
)


def test_observation_normalizes_fields_and_timestamp() -> None:
    west_africa = timezone(timedelta(hours=1))

    observation = MarketPriceObservation(
        symbol=" xauusd ",
        price=Decimal("4378.15"),
        timestamp=datetime(
            2026,
            9,
            7,
            11,
            0,
            tzinfo=west_africa,
        ),
        source=" Twelve Data ",
        price_type=PriceObservationType.MID,
    )

    assert observation.symbol == "XAUUSD"
    assert observation.price == Decimal("4378.15")
    assert observation.source == "Twelve Data"
    assert observation.price_type is PriceObservationType.MID

    assert observation.timestamp == datetime(
        2026,
        9,
        7,
        10,
        0,
        tzinfo=UTC,
    )


@pytest.mark.parametrize(
    "price",
    [
        Decimal(0),
        Decimal(-1),
    ],
)
def test_observation_rejects_nonpositive_price(
    price: Decimal,
) -> None:
    with pytest.raises(ValidationError):
        MarketPriceObservation(
            symbol="XAUUSD",
            price=price,
            timestamp=datetime(
                2026,
                9,
                7,
                10,
                0,
                tzinfo=UTC,
            ),
            source="Twelve Data",
            price_type=PriceObservationType.MID,
        )


def test_observation_rejects_empty_symbol() -> None:
    with pytest.raises(
        ValidationError,
        match="symbol must not be empty",
    ):
        MarketPriceObservation(
            symbol="   ",
            price=Decimal("4378.15"),
            timestamp=datetime(
                2026,
                9,
                7,
                10,
                0,
                tzinfo=UTC,
            ),
            source="Twelve Data",
            price_type=PriceObservationType.MID,
        )


def test_observation_rejects_empty_source() -> None:
    with pytest.raises(
        ValidationError,
        match="source must not be empty",
    ):
        MarketPriceObservation(
            symbol="XAUUSD",
            price=Decimal("4378.15"),
            timestamp=datetime(
                2026,
                9,
                7,
                10,
                0,
                tzinfo=UTC,
            ),
            source=" ",
            price_type=PriceObservationType.MID,
        )


def test_observation_rejects_naive_timestamp() -> None:
    naive_timestamp = datetime(
        2026,
        9,
        7,
        10,
        0,
        tzinfo=UTC,
    ).replace(tzinfo=None)

    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        MarketPriceObservation(
            symbol="XAUUSD",
            price=Decimal("4378.15"),
            timestamp=naive_timestamp,
            source="Twelve Data",
            price_type=PriceObservationType.MID,
        )


def test_observational_provider_is_abstract() -> None:
    with pytest.raises(TypeError):
        ObservationalMarketDataProvider()