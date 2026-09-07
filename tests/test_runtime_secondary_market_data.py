from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.execution.interfaces import (
    ExecutionProvider,
)
from packages.portfolio.position_manager import (
    PositionManager,
)
from packages.portfolio.reconciliation import (
    PortfolioReconciliationService,
)
from packages.portfolio.service import (
    PortfolioService,
)
from packages.runtime.service import (
    SecondaryMarketDataProvider,
    TradingRuntime,
)


def make_runtime(
    secondary_providers: (
        list[SecondaryMarketDataProvider] | None
    ) = None,
) -> TradingRuntime:
    execution = MagicMock(
        spec=ExecutionProvider
    )
    execution.connect = AsyncMock()
    execution.disconnect = AsyncMock()

    portfolio = MagicMock(
        spec=PortfolioService
    )

    position_manager = MagicMock(
        spec=PositionManager
    )
    position_manager.sync_all = AsyncMock()

    reconciliation = MagicMock(
        spec=PortfolioReconciliationService
    )
    reconciliation.reconcile = AsyncMock()

    scanner = MagicMock()
    scanner.scan = AsyncMock(
        return_value={
            "XAUUSD": None,
        }
    )

    return TradingRuntime(
        execution_provider=execution,
        portfolio=portfolio,
        position_manager=position_manager,
        reconciliation=reconciliation,
        scanner=scanner,
        symbols=["XAUUSD"],
        secondary_market_data_providers=(
            secondary_providers
        ),
    )


def make_secondary_provider() -> MagicMock:
    provider = MagicMock(
        spec=SecondaryMarketDataProvider
    )
    provider.connect = AsyncMock()
    provider.disconnect = AsyncMock()

    return provider


@pytest.mark.asyncio
async def test_runtime_starts_secondary_market_data_provider() -> None:
    provider = make_secondary_provider()

    runtime = make_runtime(
        [provider]
    )

    await runtime.start()

    provider.connect.assert_awaited_once()

    assert runtime.started is True

    await runtime.stop()


@pytest.mark.asyncio
async def test_runtime_disconnects_secondary_provider_on_stop() -> None:
    provider = make_secondary_provider()

    runtime = make_runtime(
        [provider]
    )

    await runtime.start()
    await runtime.stop()

    provider.disconnect.assert_awaited_once()

    assert runtime.started is False


@pytest.mark.asyncio
async def test_runtime_starts_secondaries_in_order_and_stops_reverse() -> None:
    calls: list[str] = []

    provider_one = make_secondary_provider()
    provider_two = make_secondary_provider()

    provider_one.connect.side_effect = (
        lambda: calls.append(
            "connect_one"
        )
    )
    provider_one.disconnect.side_effect = (
        lambda: calls.append(
            "disconnect_one"
        )
    )

    provider_two.connect.side_effect = (
        lambda: calls.append(
            "connect_two"
        )
    )
    provider_two.disconnect.side_effect = (
        lambda: calls.append(
            "disconnect_two"
        )
    )

    runtime = make_runtime(
        [
            provider_one,
            provider_two,
        ]
    )

    await runtime.start()

    assert calls == [
        "connect_one",
        "connect_two",
    ]

    await runtime.stop()

    assert calls == [
        "connect_one",
        "connect_two",
        "disconnect_two",
        "disconnect_one",
    ]


@pytest.mark.asyncio
async def test_runtime_rolls_back_started_secondary_provider() -> None:
    provider_one = make_secondary_provider()
    provider_two = make_secondary_provider()

    provider_two.connect.side_effect = (
        RuntimeError(
            "secondary provider failed"
        )
    )

    runtime = make_runtime(
        [
            provider_one,
            provider_two,
        ]
    )

    with pytest.raises(
        RuntimeError,
        match="secondary provider failed",
    ):
        await runtime.start()

    provider_one.connect.assert_awaited_once()
    provider_one.disconnect.assert_awaited_once()

    provider_two.connect.assert_awaited_once()
    provider_two.disconnect.assert_not_awaited()

    assert runtime.started is False


@pytest.mark.asyncio
async def test_runtime_does_not_disconnect_unstarted_secondaries() -> None:
    provider = make_secondary_provider()

    runtime = make_runtime(
        [provider]
    )

    await runtime.stop()

    provider.connect.assert_not_awaited()
    provider.disconnect.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_secondary_disconnect_failure_does_not_skip_cleanup() -> None:
    provider_one = make_secondary_provider()
    provider_two = make_secondary_provider()

    provider_two.disconnect.side_effect = (
        RuntimeError(
            "secondary disconnect failed"
        )
    )

    runtime = make_runtime(
        [
            provider_one,
            provider_two,
        ]
    )

    await runtime.start()
    await runtime.stop()

    provider_two.disconnect.assert_awaited_once()
    provider_one.disconnect.assert_awaited_once()

    assert (
        runtime.metrics().last_error
        == "secondary disconnect failed"
    )