from unittest.mock import MagicMock, patch

import pytest

from packages.market_data.mt5 import MT5MarketDataProvider


def make_symbol_info(*, visible: bool) -> MagicMock:
    info = MagicMock()
    info.visible = visible
    return info


@pytest.mark.asyncio
async def test_subscribe_quotes_does_not_claim_already_visible_symbols() -> None:
    provider = MT5MarketDataProvider()

    with patch(
        "packages.market_data.mt5.mt5.symbol_info",
        return_value=make_symbol_info(visible=True),
    ) as symbol_info, patch(
        "packages.market_data.mt5.mt5.symbol_select",
    ) as symbol_select:
        provider._connected = True

        await provider.subscribe_quotes(["EURUSD"])

    symbol_info.assert_called_once_with("EURUSD")
    symbol_select.assert_not_called()
    assert provider._owned_symbols == set()


@pytest.mark.asyncio
async def test_subscribe_quotes_claims_hidden_symbols_selected_by_provider() -> None:
    provider = MT5MarketDataProvider()

    with patch(
        "packages.market_data.mt5.mt5.symbol_info",
        return_value=make_symbol_info(visible=False),
    ) as symbol_info, patch(
        "packages.market_data.mt5.mt5.symbol_select",
        return_value=True,
    ) as symbol_select:
        provider._connected = True

        await provider.subscribe_quotes(["XAUUSD"])

    symbol_info.assert_called_once_with("XAUUSD")
    symbol_select.assert_called_once_with("XAUUSD", True)
    assert provider._owned_symbols == {"XAUUSD"}


@pytest.mark.asyncio
async def test_subscribe_quotes_deduplicates_symbols() -> None:
    provider = MT5MarketDataProvider()

    with patch(
        "packages.market_data.mt5.mt5.symbol_info",
        return_value=make_symbol_info(visible=False),
    ) as symbol_info, patch(
        "packages.market_data.mt5.mt5.symbol_select",
        return_value=True,
    ) as symbol_select:
        provider._connected = True

        await provider.subscribe_quotes(
            ["XAUUSD", "XAUUSD", "EURUSD", "XAUUSD"],
        )

    assert symbol_info.call_count == 2
    assert symbol_select.call_count == 2
    assert provider._owned_symbols == {"XAUUSD", "EURUSD"}


@pytest.mark.asyncio
async def test_unsubscribe_quotes_leaves_unowned_symbols_selected() -> None:
    provider = MT5MarketDataProvider()
    provider._connected = True

    with patch(
        "packages.market_data.mt5.mt5.symbol_select",
    ) as symbol_select:
        await provider.unsubscribe_quotes(["EURUSD"])

    symbol_select.assert_not_called()
    assert provider._owned_symbols == set()


@pytest.mark.asyncio
async def test_unsubscribe_quotes_only_removes_owned_symbols() -> None:
    provider = MT5MarketDataProvider()
    provider._connected = True
    provider._owned_symbols = {"XAUUSD"}

    with patch(
        "packages.market_data.mt5.mt5.symbol_select",
        return_value=True,
    ) as symbol_select:
        await provider.unsubscribe_quotes(
            ["EURUSD", "XAUUSD"],
        )

    symbol_select.assert_called_once_with("XAUUSD", False)
    assert provider._owned_symbols == set()


@pytest.mark.asyncio
async def test_unsubscribe_quotes_keeps_ownership_when_deselection_fails() -> None:
    provider = MT5MarketDataProvider()
    provider._connected = True
    provider._owned_symbols = {"XAUUSD"}

    with patch(
        "packages.market_data.mt5.mt5.symbol_select",
        return_value=False,
    ), patch(
        "packages.market_data.mt5.mt5.last_error",
        return_value=(-1, "Terminal: Call failed"),
    ), pytest.raises(
        RuntimeError,
        match="Failed to unsubscribe from XAUUSD",
    ):
        await provider.unsubscribe_quotes(["XAUUSD"])

    assert provider._owned_symbols == {"XAUUSD"}


@pytest.mark.asyncio
async def test_disconnect_clears_owned_symbols() -> None:
    provider = MT5MarketDataProvider()
    provider._connected = True
    provider._owned_symbols = {"XAUUSD", "GBPUSD"}

    with patch("packages.market_data.mt5.mt5.shutdown") as shutdown:
        await provider.disconnect()

    shutdown.assert_called_once()
    assert provider._connected is False
    assert provider._owned_symbols == set()