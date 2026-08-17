
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from packages.core.models import Instrument, Order
from packages.engine.scanner import DefaultMarketScanner
from packages.portfolio.instrument_registry import InstrumentRegistry

NOW = datetime.now(UTC)


def make_instrument(symbol: str) -> Instrument:
    return Instrument(
        symbol=symbol,
        name=symbol,
        asset_class="forex" if symbol == "EURUSD" else "commodity",
        tick_size=Decimal("0.01"),
        contract_size=Decimal(100),
        min_volume=Decimal("0.01"),
        volume_step=Decimal("0.01"),
        price_precision=2,
        volume_precision=2,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_scanner_processes_unique_symbols() -> None:
    engine = AsyncMock()
    engine.process_symbol.return_value = None

    scanner = DefaultMarketScanner(engine)

    results = await scanner.scan(
        ["XAUUSD", "EURUSD", "XAUUSD"]
    )

    assert results == {
        "XAUUSD": None,
        "EURUSD": None,
    }

    assert engine.process_symbol.await_count == 2


@pytest.mark.asyncio
async def test_scanner_returns_empty_for_empty_symbols() -> None:
    engine = AsyncMock()

    scanner = DefaultMarketScanner(engine)

    results = await scanner.scan([])

    assert results == {}
    engine.process_symbol.assert_not_awaited()


@pytest.mark.asyncio
async def test_scanner_calls_error_handler() -> None:
    engine = AsyncMock()
    engine.process_symbol.side_effect = RuntimeError(
        "Market data unavailable"
    )

    on_error = AsyncMock()

    scanner = DefaultMarketScanner(
        engine,
        on_error=on_error,
    )

    results = await scanner.scan(["XAUUSD"])

    assert results == {
        "XAUUSD": None,
    }

    on_error.assert_awaited_once()

    args = on_error.await_args.args

    assert args[0] == "XAUUSD"
    assert isinstance(args[1], RuntimeError)


@pytest.mark.asyncio
async def test_scanner_uses_registry_when_symbols_are_omitted() -> None:
    engine = AsyncMock()
    engine.process_symbol.return_value = None

    registry = InstrumentRegistry(
        [
            make_instrument("XAUUSD"),
            make_instrument("EURUSD"),
            make_instrument("GBPUSD"),
        ]
    )

    registry.disable("GBPUSD")

    scanner = DefaultMarketScanner(
        engine,
        registry=registry,
    )

    results = await scanner.scan()

    assert results == {
        "XAUUSD": None,
        "EURUSD": None,
    }

    assert engine.process_symbol.await_count == 2


@pytest.mark.asyncio
async def test_scanner_skips_disabled_registry_symbols() -> None:
    engine = AsyncMock()
    engine.process_symbol.return_value = None

    registry = InstrumentRegistry(
        [
            make_instrument("XAUUSD"),
            make_instrument("EURUSD"),
        ]
    )

    registry.disable("EURUSD")

    scanner = DefaultMarketScanner(
        engine,
        registry=registry,
    )

    results = await scanner.scan(
        ["XAUUSD", "EURUSD"]
    )

    assert results == {
        "XAUUSD": None,
    }

    engine.process_symbol.assert_awaited_once_with(
        "XAUUSD"
    )


@pytest.mark.asyncio
async def test_scanner_without_symbols_or_registry_raises() -> None:
    engine = AsyncMock()

    scanner = DefaultMarketScanner(engine)

    with pytest.raises(
        ValueError,
        match="symbols or an instrument registry is required",
    ):
        await scanner.scan()


@pytest.mark.asyncio
async def test_scanner_preserves_order_results() -> None:
    engine = AsyncMock()

    first_order = Order.model_construct(
        symbol="XAUUSD",
    )
    second_order = Order.model_construct(
        symbol="EURUSD",
    )

    engine.process_symbol.side_effect = [
        first_order,
        second_order,
    ]

    scanner = DefaultMarketScanner(engine)

    results = await scanner.scan(
        ["XAUUSD", "EURUSD"]
    )

    assert results["XAUUSD"] is first_order
    assert results["EURUSD"] is second_order

