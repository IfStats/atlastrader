from packages.market_data.base import MarketDataProvider
from packages.market_data.mock import MockMarketDataProvider
from packages.market_data.mt5 import MT5MarketDataProvider


def test_mock_provider_implements_market_data_provider() -> None:
    assert issubclass(MockMarketDataProvider, MarketDataProvider)


def test_mt5_provider_implements_market_data_provider() -> None:
    assert issubclass(MT5MarketDataProvider, MarketDataProvider)


def test_market_data_provider_is_abstract() -> None:
    assert MarketDataProvider.__abstractmethods__ == {
        "get_quote",
        "get_candles",
        "subscribe_quotes",
        "unsubscribe_quotes",
    }