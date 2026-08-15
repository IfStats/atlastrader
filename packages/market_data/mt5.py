from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, ClassVar

import MetaTrader5 as mt5  # type: ignore[import-untyped]

from packages.core.enums import Timeframe
from packages.core.models import Candle, Quote
from packages.market_data.base import MarketDataProvider


class MT5MarketDataProvider(MarketDataProvider):
    """Market-data adapter for MetaTrader 5."""

    _TIMEFRAME_MAP: ClassVar[dict[Timeframe, int]] = {
        Timeframe.M1: mt5.TIMEFRAME_M1,
        Timeframe.M5: mt5.TIMEFRAME_M5,
        Timeframe.M15: mt5.TIMEFRAME_M15,
        Timeframe.M30: mt5.TIMEFRAME_M30,
        Timeframe.H1: mt5.TIMEFRAME_H1,
        Timeframe.H4: mt5.TIMEFRAME_H4,
        Timeframe.D1: mt5.TIMEFRAME_D1,
    }

    def __init__(self) -> None:
        self._connected = False

    async def connect(self) -> None:
        """Initialize the MetaTrader 5 terminal connection."""

        if self._connected:
            return

        if not mt5.initialize():
            error = mt5.last_error()
            raise RuntimeError(
                f"Failed to initialize MetaTrader 5: {error}"
            )

        self._connected = True

    async def disconnect(self) -> None:
        """Shutdown the MetaTrader 5 terminal connection."""

        if not self._connected:
            return

        mt5.shutdown()
        self._connected = False

    async def get_quote(self, symbol: str) -> Quote:
        """Return the latest normalized quote."""

        self._require_connection()

        tick = mt5.symbol_info_tick(symbol)

        if tick is None:
            error = mt5.last_error()
            raise RuntimeError(
                f"Failed to retrieve quote for {symbol}: {error}"
            )

        if tick.bid <= 0 or tick.ask <= 0:
            raise RuntimeError(
                f"Invalid quote received for {symbol}"
            )

        timestamp = datetime.fromtimestamp(
            int(tick.time),
            tz=UTC,
        )

        return Quote(
            symbol=symbol,
            bid=Decimal(str(tick.bid)),
            ask=Decimal(str(tick.ask)),
            timestamp=timestamp,
        )

    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        """Return historical candles ordered from oldest to newest."""

        self._require_connection()

        if start >= end:
            raise ValueError("start must be earlier than end")

        mt5_timeframe = self._TIMEFRAME_MAP[timeframe]

        rates = mt5.copy_rates_range(
            symbol,
            mt5_timeframe,
            start,
            end,
        )

        if rates is None:
            error = mt5.last_error()
            raise RuntimeError(
                f"Failed to retrieve candles for {symbol}: {error}"
            )

        candles = [
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=datetime.fromtimestamp(
                    int(rate["time"]),
                    tz=UTC,
                ),
                open=Decimal(str(rate["open"])),
                high=Decimal(str(rate["high"])),
                low=Decimal(str(rate["low"])),
                close=Decimal(str(rate["close"])),
                volume=Decimal(str(rate["tick_volume"])),
            )
            for rate in rates
        ]

        return sorted(
            candles,
            key=lambda candle: candle.timestamp,
        )

    async def subscribe_quotes(
        self,
        symbols: list[str],
    ) -> None:
        """Ensure requested symbols are available in MetaTrader 5."""

        self._require_connection()

        for symbol in symbols:
            if not mt5.symbol_select(symbol, True):
                error = mt5.last_error()
                raise RuntimeError(
                    f"Failed to subscribe to {symbol}: {error}"
                )

    async def unsubscribe_quotes(
        self,
        symbols: list[str],
    ) -> None:
        """Remove requested symbols from the MetaTrader 5 watchlist."""

        self._require_connection()

        for symbol in symbols:
            if not mt5.symbol_select(symbol, False):
                error = mt5.last_error()
                raise RuntimeError(
                    f"Failed to unsubscribe from {symbol}: {error}"
                )

    def _require_connection(self) -> None:
        """Raise when the provider is not connected."""

        if not self._connected:
            raise RuntimeError(
                "Market-data provider is not connected"
            )

    @staticmethod
    def _normalize_rate_value(
        rate: Any,
        field: str,
    ) -> Decimal:
        """Normalize a numeric MT5 rate field to Decimal."""

        return Decimal(str(rate[field]))