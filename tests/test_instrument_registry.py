from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.core.models import Instrument
from packages.portfolio.instrument_registry import InstrumentRegistry

NOW = datetime.now(UTC)


def make_instrument(
    symbol: str = "XAUUSD",
) -> Instrument:
    return Instrument(
        symbol=symbol,
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


def test_registry_starts_empty() -> None:
    registry = InstrumentRegistry()

    assert len(registry) == 0
    assert registry.all() == []
    assert registry.symbols() == []


def test_registry_registers_instrument() -> None:
    instrument = make_instrument()

    registry = InstrumentRegistry()

    registry.register(instrument)

    assert len(registry) == 1
    assert registry.get("XAUUSD") is instrument
    assert registry.contains("XAUUSD")


def test_registry_accepts_initial_instruments() -> None:
    gold = make_instrument("XAUUSD")
    silver = make_instrument("XAGUSD")

    registry = InstrumentRegistry(
        [gold, silver]
    )

    assert registry.symbols() == [
        "XAUUSD",
        "XAGUSD",
    ]


def test_registry_replaces_existing_symbol() -> None:
    first = make_instrument("XAUUSD")
    second = make_instrument("XAUUSD")

    registry = InstrumentRegistry([first])

    registry.register(second)

    assert len(registry) == 1
    assert registry.get("XAUUSD") is second


def test_registry_rejects_empty_symbol() -> None:
    instrument = make_instrument("")

    registry = InstrumentRegistry()

    with pytest.raises(
        ValueError,
        match="Instrument symbol cannot be empty",
    ):
        registry.register(instrument)


def test_registry_rejects_whitespace_in_symbol() -> None:
    instrument = make_instrument(" XAUUSD ")

    registry = InstrumentRegistry()

    with pytest.raises(
        ValueError,
        match="leading or trailing whitespace",
    ):
        registry.register(instrument)


def test_registry_raises_for_unknown_symbol() -> None:
    registry = InstrumentRegistry()

    with pytest.raises(
        KeyError,
        match="Instrument not found: XAUUSD",
    ):
        registry.get("XAUUSD")


def test_registry_unregisters_instrument() -> None:
    instrument = make_instrument()

    registry = InstrumentRegistry([instrument])

    registry.unregister("XAUUSD")

    assert len(registry) == 0
    assert not registry.contains("XAUUSD")


def test_registry_unregister_unknown_symbol_raises() -> None:
    registry = InstrumentRegistry()

    with pytest.raises(
        KeyError,
        match="Instrument not found: XAUUSD",
    ):
        registry.unregister("XAUUSD")


def test_registry_returns_registered_symbols() -> None:
    registry = InstrumentRegistry(
        [
            make_instrument("XAUUSD"),
            make_instrument("EURUSD"),
            make_instrument("BTCUSD"),
        ]
    )

    assert registry.symbols() == [
        "XAUUSD",
        "EURUSD",
        "BTCUSD",
    ]

def test_registry_filters_by_asset_class() -> None:
    registry = InstrumentRegistry(
        [
            make_instrument("XAUUSD"),
            make_instrument("XAGUSD"),
            make_instrument("EURUSD"),
        ]
    )

    registry.get("XAUUSD").asset_class = "commodity"
    registry.get("XAGUSD").asset_class = "commodity"
    registry.get("EURUSD").asset_class = "forex"

    commodities = registry.get_by_asset_class("commodity")

    assert [instrument.symbol for instrument in commodities] == [
        "XAUUSD",
        "XAGUSD",
    ]


def test_registry_asset_class_filter_is_case_insensitive() -> None:
    registry = InstrumentRegistry(
        [make_instrument("XAUUSD")]
    )

    assert [
        instrument.symbol
        for instrument in registry.get_by_asset_class("COMMODITY")
    ] == ["XAUUSD"]


def test_registry_can_disable_instrument() -> None:
    registry = InstrumentRegistry(
        [make_instrument("XAUUSD")]
    )

    registry.disable("XAUUSD")

    assert registry.is_enabled("XAUUSD") is False
    assert registry.tradable() == []
    assert registry.tradable_symbols() == []


def test_registry_can_reenable_instrument() -> None:
    registry = InstrumentRegistry(
        [make_instrument("XAUUSD")]
    )

    registry.disable("XAUUSD")
    registry.enable("XAUUSD")

    assert registry.is_enabled("XAUUSD") is True
    assert registry.tradable_symbols() == ["XAUUSD"]


def test_registry_tradable_asset_class_filter() -> None:
    registry = InstrumentRegistry(
        [
            make_instrument("XAUUSD"),
            make_instrument("XAGUSD"),
        ]
    )

    registry.disable("XAGUSD")

    instruments = registry.tradable_by_asset_class(
        "commodity"
    )

    assert [instrument.symbol for instrument in instruments] == [
        "XAUUSD"
    ]


def test_registry_enable_unknown_symbol_raises() -> None:
    registry = InstrumentRegistry()

    with pytest.raises(
        KeyError,
        match="Instrument not found: XAUUSD",
    ):
        registry.enable("XAUUSD")


def test_registry_disable_unknown_symbol_raises() -> None:
    registry = InstrumentRegistry()

    with pytest.raises(
        KeyError,
        match="Instrument not found: XAUUSD",
    ):
        registry.disable("XAUUSD")


def test_registry_rejects_empty_asset_class_filter() -> None:
    registry = InstrumentRegistry(
        [make_instrument("XAUUSD")]
    )

    with pytest.raises(
        ValueError,
        match="asset_class cannot be empty",
    ):
        registry.get_by_asset_class("   ")