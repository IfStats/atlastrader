from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.core.models import Instrument
from packages.risk.position_sizer import DefaultPositionSizer

NOW = datetime.now(UTC)


def make_instrument() -> Instrument:
    return Instrument(
        symbol="XAUUSD",
        name="Gold",
        asset_class="commodity",
        tick_size=Decimal("0.01"),
        contract_size=Decimal(100),
        min_volume=Decimal("0.01"),
        volume_step=Decimal("0.01"),
        price_precision=2,
        volume_precision=2,
        created_at=NOW,
        updated_at=NOW,
    )


def make_sizer() -> DefaultPositionSizer:
    return DefaultPositionSizer()


def test_calculates_risk_based_volume() -> None:
    sizer = make_sizer()

    volume = sizer.calculate_volume(
        equity=Decimal(10000),
        risk_percent=Decimal(1),
        entry_price=Decimal(3350),
        stop_loss_price=Decimal(3340),
        instrument=make_instrument(),
    )

    assert volume == Decimal("0.10")


def test_normalizes_volume_to_step() -> None:
    sizer = make_sizer()

    volume = sizer.calculate_volume(
        equity=Decimal(10000),
        risk_percent=Decimal(1),
        entry_price=Decimal(3350),
        stop_loss_price=Decimal("3344.7"),
        instrument=make_instrument(),
    )

    assert volume == Decimal("0.18")


def test_enforces_minimum_volume() -> None:
    sizer = make_sizer()

    volume = sizer.calculate_volume(
        equity=Decimal(100),
        risk_percent=Decimal("0.1"),
        entry_price=Decimal(3350),
        stop_loss_price=Decimal(3340),
        instrument=make_instrument(),
    )

    assert volume == Decimal("0.01")


@pytest.mark.parametrize(
    ("equity", "risk_percent"),
    [
        (Decimal(0), Decimal(1)),
        (Decimal(-100), Decimal(1)),
        (Decimal(10000), Decimal(0)),
        (Decimal(10000), Decimal(-1)),
    ],
)
def test_rejects_invalid_risk_inputs(
    equity: Decimal,
    risk_percent: Decimal,
) -> None:
    with pytest.raises(ValueError):
        make_sizer().calculate_volume(
            equity=equity,
            risk_percent=risk_percent,
            entry_price=Decimal(3350),
            stop_loss_price=Decimal(3340),
            instrument=make_instrument(),
        )


def test_rejects_zero_stop_distance() -> None:
    with pytest.raises(ValueError, match="stop-loss distance"):
        make_sizer().calculate_volume(
            equity=Decimal(10000),
            risk_percent=Decimal(1),
            entry_price=Decimal(3350),
            stop_loss_price=Decimal(3350),
            instrument=make_instrument(),
        )


def test_rejects_invalid_prices() -> None:
    with pytest.raises(ValueError):
        make_sizer().calculate_volume(
            equity=Decimal(10000),
            risk_percent=Decimal(1),
            entry_price=Decimal(0),
            stop_loss_price=Decimal(3340),
            instrument=make_instrument(),
        )