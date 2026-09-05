from unittest.mock import AsyncMock

import pytest

from packages.engine.scanner import DefaultMarketScanner


@pytest.mark.asyncio
async def test_scanner_uses_standard_processing_by_default() -> None:
    engine = AsyncMock()

    engine.process_symbol.return_value = None

    scanner = DefaultMarketScanner(engine)

    result = await scanner.scan(["XAUUSD", "EURUSD"])

    assert result == {
        "XAUUSD": None,
        "EURUSD": None,
    }

    assert engine.process_symbol.await_count == 2
    engine.process_symbol.assert_any_await("XAUUSD")
    engine.process_symbol.assert_any_await("EURUSD")
    engine.process_autonomous_symbol.assert_not_awaited()


@pytest.mark.asyncio
async def test_scanner_uses_autonomous_processing_when_enabled() -> None:
    engine = AsyncMock()

    engine.process_autonomous_symbol.return_value = None

    scanner = DefaultMarketScanner(
        engine,
        autonomous=True,
    )

    result = await scanner.scan(["XAUUSD", "EURUSD"])

    assert result == {
        "XAUUSD": None,
        "EURUSD": None,
    }

    assert engine.process_autonomous_symbol.await_count == 2
    engine.process_autonomous_symbol.assert_any_await("XAUUSD")
    engine.process_autonomous_symbol.assert_any_await("EURUSD")
    engine.process_symbol.assert_not_awaited()


@pytest.mark.asyncio
async def test_scanner_deduplicates_symbols() -> None:
    engine = AsyncMock()
    engine.process_autonomous_symbol.return_value = None

    scanner = DefaultMarketScanner(
        engine,
        autonomous=True,
    )

    result = await scanner.scan(
        ["XAUUSD", "XAUUSD", "EURUSD", "EURUSD"]
    )

    assert result == {
        "XAUUSD": None,
        "EURUSD": None,
    }

    assert engine.process_autonomous_symbol.await_count == 2


@pytest.mark.asyncio
async def test_scanner_isolates_symbol_runtime_errors() -> None:
    engine = AsyncMock()

    async def process(symbol: str) -> None:
        if symbol == "XAUUSD":
            raise RuntimeError("market context unavailable")

    engine.process_autonomous_symbol.side_effect = process

    on_error = AsyncMock()

    scanner = DefaultMarketScanner(
        engine,
        autonomous=True,
        on_error=on_error,
    )

    result = await scanner.scan(["XAUUSD", "EURUSD"])

    assert result == {
        "XAUUSD": None,
        "EURUSD": None,
    }

    on_error.assert_awaited_once()
    assert on_error.await_args.args[0] == "XAUUSD"
    assert isinstance(on_error.await_args.args[1], RuntimeError)


@pytest.mark.asyncio
async def test_scanner_returns_empty_result_for_empty_symbols() -> None:
    engine = AsyncMock()

    scanner = DefaultMarketScanner(
        engine,
        autonomous=True,
    )

    result = await scanner.scan([])

    assert result == {}
    engine.process_autonomous_symbol.assert_not_awaited()