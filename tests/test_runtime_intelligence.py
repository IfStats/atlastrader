from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.execution.interfaces import ExecutionProvider
from packages.intelligence.interfaces import MarketIntelligenceProvider
from packages.portfolio.position_manager import PositionManager
from packages.portfolio.reconciliation import PortfolioReconciliationService
from packages.portfolio.service import PortfolioService
from packages.runtime.service import TradingRuntime


def make_runtime(
    intelligence_providers: list[MarketIntelligenceProvider] | None = None,
) -> TradingRuntime:
    execution = MagicMock(spec=ExecutionProvider)
    execution.connect = AsyncMock()
    execution.disconnect = AsyncMock()

    portfolio = MagicMock(spec=PortfolioService)

    position_manager = MagicMock(spec=PositionManager)
    position_manager.sync_all = AsyncMock()

    reconciliation = MagicMock(spec=PortfolioReconciliationService)
    reconciliation.reconcile = AsyncMock()

    scanner = MagicMock()
    scanner.scan = AsyncMock(return_value={"XAUUSD": None})

    return TradingRuntime(
        execution_provider=execution,
        portfolio=portfolio,
        position_manager=position_manager,
        reconciliation=reconciliation,
        scanner=scanner,
        symbols=["XAUUSD"],
        intelligence_providers=intelligence_providers,
    )


@pytest.mark.asyncio
async def test_runtime_starts_intelligence_provider() -> None:
    provider = MagicMock(spec=MarketIntelligenceProvider)
    provider.start = AsyncMock()
    provider.close = AsyncMock()

    runtime = make_runtime([provider])

    await runtime.start()

    provider.start.assert_awaited_once()
    assert runtime.started is True

    await runtime.stop()


@pytest.mark.asyncio
async def test_runtime_closes_intelligence_provider_on_stop() -> None:
    provider = MagicMock(spec=MarketIntelligenceProvider)
    provider.start = AsyncMock()
    provider.close = AsyncMock()

    runtime = make_runtime([provider])

    await runtime.start()
    await runtime.stop()

    provider.close.assert_awaited_once()
    assert runtime.started is False


@pytest.mark.asyncio
async def test_runtime_starts_multiple_intelligence_providers_in_order() -> None:
    calls: list[str] = []

    provider_one = MagicMock(spec=MarketIntelligenceProvider)
    provider_one.start = AsyncMock(
        side_effect=lambda: calls.append("start_one"),
    )
    provider_one.close = AsyncMock(
        side_effect=lambda: calls.append("close_one"),
    )

    provider_two = MagicMock(spec=MarketIntelligenceProvider)
    provider_two.start = AsyncMock(
        side_effect=lambda: calls.append("start_two"),
    )
    provider_two.close = AsyncMock(
        side_effect=lambda: calls.append("close_two"),
    )

    runtime = make_runtime([provider_one, provider_two])

    await runtime.start()

    assert calls == ["start_one", "start_two"]

    await runtime.stop()

    assert calls == [
        "start_one",
        "start_two",
        "close_two",
        "close_one",
    ]


@pytest.mark.asyncio
async def test_runtime_rolls_back_started_intelligence_providers() -> None:
    provider_one = MagicMock(spec=MarketIntelligenceProvider)
    provider_one.start = AsyncMock()
    provider_one.close = AsyncMock()

    provider_two = MagicMock(spec=MarketIntelligenceProvider)
    provider_two.start = AsyncMock(
        side_effect=RuntimeError("provider two failed"),
    )
    provider_two.close = AsyncMock()

    runtime = make_runtime([provider_one, provider_two])

    with pytest.raises(RuntimeError, match="provider two failed"):
        await runtime.start()

    provider_one.start.assert_awaited_once()
    provider_one.close.assert_awaited_once()
    provider_two.start.assert_awaited_once()
    provider_two.close.assert_not_awaited()

    assert runtime.started is False


@pytest.mark.asyncio
async def test_runtime_supports_provider_without_lifecycle_methods() -> None:
    provider = MagicMock(spec=MarketIntelligenceProvider)

    runtime = make_runtime([provider])

    await runtime.start()

    assert runtime.started is True

    await runtime.stop()

    assert runtime.started is False