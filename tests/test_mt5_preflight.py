from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.enums import AssetClass
from packages.core.models import (
    Instrument,
    MT5AccountSnapshot,
    MT5TerminalSnapshot,
    Quote,
)
from packages.execution.preflight import MT5Preflight


def make_instrument(
    symbol: str = "XAUUSD",
) -> Instrument:
    return Instrument(
        symbol=symbol,
        name=symbol,
        asset_class=AssetClass.METAL,
        quote_currency="USD",
        broker_symbol=symbol,
        tick_size=Decimal("0.01"),
        contract_size=Decimal(100),
        min_volume=Decimal("0.01"),
        max_volume=Decimal(100),
        volume_step=Decimal("0.01"),
        price_precision=2,
        volume_precision=2,
        enabled=True,
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )


def make_terminal(
    *,
    trade_allowed: bool = True,
) -> MT5TerminalSnapshot:
    return MT5TerminalSnapshot(
        connected=True,
        trade_allowed=trade_allowed,
        tradeapi_disabled=False,
        build=6157,
        name="MetaTrader 5",
    )


def make_account(
    *,
    trade_allowed: bool = True,
    trade_expert: bool = True,
) -> MT5AccountSnapshot:
    return MT5AccountSnapshot(
        login=123456,
        server="Fusion Markets-Demo",
        currency="USD",
        balance=Decimal(10000),
        equity=Decimal(10000),
        margin=Decimal(0),
        free_margin=Decimal(10000),
        leverage=500,
        trade_allowed=trade_allowed,
        trade_expert=trade_expert,
    )


@pytest.fixture
def execution() -> MagicMock:
    provider = MagicMock()
    provider.is_connected = AsyncMock(return_value=True)
    provider.get_terminal_snapshot = AsyncMock(
        return_value=make_terminal()
    )
    provider.get_account_snapshot = AsyncMock(
        return_value=make_account()
    )
    provider.get_instrument = AsyncMock(
        return_value=make_instrument()
    )
    provider.get_positions = AsyncMock(return_value=[])
    return provider


@pytest.fixture
def market_data() -> MagicMock:
    provider = MagicMock()
    provider.get_quote = AsyncMock(
        return_value=Quote(
            symbol="XAUUSD",
            bid=Decimal("4329.36"),
            ask=Decimal("4329.49"),
            timestamp=MagicMock(),
        )
    )
    return provider


@pytest.mark.asyncio
async def test_preflight_passes_when_environment_is_ready(
    execution: MagicMock,
    market_data: MagicMock,
) -> None:
    preflight = MT5Preflight(
        execution_provider=execution,
        market_data_provider=market_data,
        symbols=["XAUUSD"],
    )

    result = await preflight.run()

    assert result.ready is True
    assert result.blockers == []
    assert result.checks["terminal_connected"] is True
    assert result.checks["instrument:XAUUSD"] is True
    assert result.checks["quote:XAUUSD"] is True


@pytest.mark.asyncio
async def test_preflight_blocks_when_terminal_trading_is_disabled(
    execution: MagicMock,
    market_data: MagicMock,
) -> None:
    execution.get_terminal_snapshot.return_value = make_terminal(
        trade_allowed=False
    )

    preflight = MT5Preflight(
        execution_provider=execution,
        market_data_provider=market_data,
        symbols=["XAUUSD"],
    )

    result = await preflight.run()

    assert result.ready is False
    assert "MT5 terminal trading is disabled" in result.blockers


@pytest.mark.asyncio
async def test_preflight_blocks_when_account_trading_is_disabled(
    execution: MagicMock,
    market_data: MagicMock,
) -> None:
    execution.get_account_snapshot.return_value = make_account(
        trade_allowed=False
    )

    preflight = MT5Preflight(
        execution_provider=execution,
        market_data_provider=market_data,
        symbols=["XAUUSD"],
    )

    result = await preflight.run()

    assert result.ready is False
    assert "MT5 account trading is not allowed" in result.blockers


@pytest.mark.asyncio
async def test_preflight_blocks_invalid_quote(
    execution: MagicMock,
    market_data: MagicMock,
) -> None:
    market_data.get_quote.side_effect = RuntimeError(
        "Quote unavailable"
    )

    preflight = MT5Preflight(
        execution_provider=execution,
        market_data_provider=market_data,
        symbols=["XAUUSD"],
    )

    result = await preflight.run()

    assert result.ready is False
    assert result.checks["quote:XAUUSD"] is False
    assert "Quote unavailable or invalid: XAUUSD" in result.blockers


@pytest.mark.asyncio
async def test_preflight_reads_positions(
    execution: MagicMock,
    market_data: MagicMock,
) -> None:
    execution.get_positions.return_value = []

    preflight = MT5Preflight(
        execution_provider=execution,
        market_data_provider=market_data,
        symbols=["XAUUSD"],
    )

    result = await preflight.run()

    execution.get_positions.assert_awaited_once()
    assert result.positions == []