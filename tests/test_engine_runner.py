import asyncio
from unittest.mock import AsyncMock

import pytest

from packages.engine.runner import MarketScannerRunner


@pytest.mark.asyncio
async def test_runner_requires_symbols() -> None:
    scanner = AsyncMock()

    with pytest.raises(
        ValueError,
        match="At least one symbol is required",
    ):
        MarketScannerRunner(
            scanner,
            [],
        )


@pytest.mark.asyncio
async def test_runner_requires_positive_interval() -> None:
    scanner = AsyncMock()

    with pytest.raises(
        ValueError,
        match="interval_seconds must be greater than zero",
    ):
        MarketScannerRunner(
            scanner,
            ["XAUUSD"],
            interval_seconds=0,
        )


@pytest.mark.asyncio
async def test_runner_deduplicates_symbols() -> None:
    scanner = AsyncMock()

    runner = MarketScannerRunner(
        scanner,
        ["XAUUSD", "EURUSD", "XAUUSD"],
    )

    assert runner.symbols == [
        "XAUUSD",
        "EURUSD",
    ]


@pytest.mark.asyncio
async def test_runner_start_and_stop() -> None:
    scanner = AsyncMock()
    scanner.scan.return_value = {
        "XAUUSD": None,
    }

    runner = MarketScannerRunner(
        scanner,
        ["XAUUSD"],
        interval_seconds=60,
    )

    assert runner.is_running is False

    await runner.start()

    assert runner.is_running is True

    await asyncio.sleep(0.01)

    await runner.stop()

    assert runner.is_running is False
    scanner.scan.assert_awaited()


@pytest.mark.asyncio
async def test_runner_does_not_start_twice() -> None:
    scanner = AsyncMock()
    scanner.scan.return_value = {}

    runner = MarketScannerRunner(
        scanner,
        ["XAUUSD"],
        interval_seconds=60,
    )

    await runner.start()

    first_task = runner._task

    await runner.start()

    assert runner._task is first_task

    await runner.stop()


@pytest.mark.asyncio
async def test_runner_calls_on_cycle() -> None:
    scanner = AsyncMock()
    scanner.scan.return_value = {
        "XAUUSD": None,
    }

    on_cycle = AsyncMock()

    runner = MarketScannerRunner(
        scanner,
        ["XAUUSD"],
        interval_seconds=60,
        on_cycle=on_cycle,
    )

    await runner.start()

    await asyncio.sleep(0.01)

    await runner.stop()

    on_cycle.assert_awaited_once_with(
        {"XAUUSD": None}
    )
