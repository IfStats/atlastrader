from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar

from packages.core.enums import Timeframe
from packages.core.models import Candle, Quote
from packages.market_data.base import MarketDataProvider
from packages.market_data.http import MarketDataHTTPTransport


class MassiveMarketDataProvider(MarketDataProvider):
    """REST market-data adapter for Massive forex and metal currency pairs."""

    _TIMEFRAME_MAP: ClassVar[dict[Timeframe, tuple[int, str]]] = {
        Timeframe.M1: (1, "minute"),
        Timeframe.M5: (5, "minute"),
        Timeframe.M15: (15, "minute"),
        Timeframe.M30: (30, "minute"),
        Timeframe.H1: (1, "hour"),
        Timeframe.H4: (4, "hour"),
        Timeframe.D1: (1, "day"),
    }

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.massive.com",
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        backoff_seconds: float = 0.5,
        transport: MarketDataHTTPTransport | None = None,
    ) -> None:
        normalized_api_key = api_key.strip()

        if not normalized_api_key:
            raise ValueError("api_key must not be empty")

        self._transport = transport or MarketDataHTTPTransport(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {normalized_api_key}",
            },
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
        )

        self._owns_transport = transport is None
        self._connected = False
        self._subscribed_symbols: set[str] = set()

    async def connect(self) -> None:
        """Start the underlying HTTP transport."""
        if self._connected:
            return

        if self._owns_transport:
            await self._transport.start()

        self._connected = True

    async def disconnect(self) -> None:
        """Close the owned HTTP transport and clear local subscriptions."""
        if not self._connected:
            return

        if self._owns_transport:
            await self._transport.close()

        self._subscribed_symbols.clear()
        self._connected = False

    async def get_quote(self, symbol: str) -> Quote:
        """Return the latest normalized bid/ask quote."""
        self._require_connection()

        base, quote, canonical_symbol = self._parse_pair_symbol(
            symbol
        )

        payload = self._require_mapping(
            await self._transport.get_json(
                f"/v1/last_quote/currencies/{base}/{quote}"
            ),
            context="quote response",
        )

        last = self._require_mapping(
            payload.get("last"),
            context="quote response 'last'",
        )

        bid = self._require_positive_decimal(
            last,
            "bid",
        )
        ask = self._require_positive_decimal(
            last,
            "ask",
        )

        if ask < bid:
            raise RuntimeError(
                f"Massive returned ask below bid for "
                f"{canonical_symbol}"
            )

        timestamp_ms = self._require_positive_int(
            last,
            "timestamp",
        )

        return Quote(
            symbol=canonical_symbol,
            bid=bid,
            ask=ask,
            timestamp=self._timestamp_from_milliseconds(
                timestamp_ms
            ),
        )

    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        """Return Massive forex aggregate bars ordered oldest to newest."""
        self._require_connection()

        start_utc = self._normalize_datetime(start)
        end_utc = self._normalize_datetime(end)

        if start_utc >= end_utc:
            raise ValueError(
                "start must be earlier than end"
            )

        _, _, canonical_symbol = self._parse_pair_symbol(
            symbol
        )

        multiplier, timespan = self._TIMEFRAME_MAP[
            timeframe
        ]

        start_ms = self._to_unix_milliseconds(
            start_utc
        )
        end_ms = self._to_unix_milliseconds(
            end_utc
        )

        payload = self._require_mapping(
            await self._transport.get_json(
                (
                    f"/v2/aggs/ticker/C:{canonical_symbol}/"
                    f"range/{multiplier}/{timespan}/"
                    f"{start_ms}/{end_ms}"
                ),
                params={
                    "adjusted": "true",
                    "sort": "asc",
                    "limit": 50000,
                },
            ),
            context="aggregate response",
        )

        raw_results = payload.get(
            "results",
            [],
        )

        if raw_results is None:
            return []

        if not isinstance(raw_results, list):
            raise TypeError(
                "Massive aggregate response "
                "'results' must be a list"
            )

        candles: list[Candle] = []

        for raw_result in raw_results:
            result = self._require_mapping(
                raw_result,
                context="aggregate result",
            )

            candles.append(
                Candle(
                    symbol=canonical_symbol,
                    timeframe=timeframe,
                    timestamp=(
                        self._timestamp_from_milliseconds(
                            self._require_positive_int(
                                result,
                                "t",
                            )
                        )
                    ),
                    open=self._require_positive_decimal(
                        result,
                        "o",
                    ),
                    high=self._require_positive_decimal(
                        result,
                        "h",
                    ),
                    low=self._require_positive_decimal(
                        result,
                        "l",
                    ),
                    close=self._require_positive_decimal(
                        result,
                        "c",
                    ),
                    volume=(
                        self._optional_nonnegative_decimal(
                            result,
                            "v",
                        )
                    ),
                )
            )

        return sorted(
            candles,
            key=lambda candle: candle.timestamp,
        )

    async def subscribe_quotes(
        self,
        symbols: list[str],
    ) -> None:
        """Register symbols for a later streaming or polling layer."""
        self._require_connection()

        if not symbols:
            raise ValueError(
                "At least one symbol is required"
            )

        normalized_symbols = {
            self._parse_pair_symbol(symbol)[2]
            for symbol in symbols
        }

        self._subscribed_symbols.update(
            normalized_symbols
        )

    async def unsubscribe_quotes(
        self,
        symbols: list[str],
    ) -> None:
        """Remove symbols from the local subscription registry."""
        self._require_connection()

        if not symbols:
            return

        normalized_symbols = {
            self._parse_pair_symbol(symbol)[2]
            for symbol in symbols
        }

        self._subscribed_symbols.difference_update(
            normalized_symbols
        )

    def _require_connection(self) -> None:
        """Raise when the provider has not been connected."""
        if not self._connected:
            raise RuntimeError(
                "Market-data provider is not connected"
            )

    @staticmethod
    def _parse_pair_symbol(
        symbol: str,
    ) -> tuple[str, str, str]:
        """Normalize a six-letter currency or metal pair."""
        normalized = symbol.strip().upper()

        normalized = normalized.removeprefix("C:")

        normalized = (
            normalized
            .replace("/", "")
            .replace("-", "")
        )

        if (
            len(normalized) != 6
            or not normalized.isalpha()
        ):
            raise ValueError(
                "Massive pair symbols must contain "
                "two three-letter codes"
            )

        base = normalized[:3]
        quote = normalized[3:]

        return base, quote, normalized

    @staticmethod
    def _normalize_datetime(
        value: datetime,
    ) -> datetime:
        """Return a UTC-aware datetime."""
        if value.tzinfo is None:
            return value.replace(
                tzinfo=UTC
            )

        return value.astimezone(UTC)

    @staticmethod
    def _to_unix_milliseconds(
        value: datetime,
    ) -> int:
        """Convert a datetime to Unix milliseconds."""
        return int(
            value.timestamp() * 1000
        )

    @staticmethod
    def _timestamp_from_milliseconds(
        timestamp_ms: int,
    ) -> datetime:
        """Convert Unix milliseconds to a UTC datetime."""
        return datetime.fromtimestamp(
            timestamp_ms / 1000,
            tz=UTC,
        )

    @staticmethod
    def _require_mapping(
        value: Any,
        *,
        context: str,
    ) -> Mapping[str, Any]:
        """Validate that a provider payload component is an object."""
        if not isinstance(
            value,
            Mapping,
        ):
            raise TypeError(
                f"Massive {context} must be an object"
            )

        return value

    @staticmethod
    def _require_positive_decimal(
        data: Mapping[str, Any],
        field: str,
    ) -> Decimal:
        """Read a required positive decimal field."""
        if field not in data:
            raise RuntimeError(
                f"Massive response is missing '{field}'"
            )

        try:
            value = Decimal(
                str(data[field])
            )
        except (
            InvalidOperation,
            ValueError,
        ) as exc:
            raise RuntimeError(
                f"Massive response field "
                f"'{field}' is invalid"
            ) from exc

        if value <= 0:
            raise RuntimeError(
                f"Massive response field '{field}' "
                "must be greater than zero"
            )

        return value

    @staticmethod
    def _optional_nonnegative_decimal(
        data: Mapping[str, Any],
        field: str,
    ) -> Decimal:
        """Read an optional non-negative decimal field."""
        raw_value = data.get(
            field,
            0,
        )

        try:
            value = Decimal(
                str(raw_value)
            )
        except (
            InvalidOperation,
            ValueError,
        ) as exc:
            raise RuntimeError(
                f"Massive response field "
                f"'{field}' is invalid"
            ) from exc

        if value < 0:
            raise RuntimeError(
                f"Massive response field '{field}' "
                "must not be negative"
            )

        return value

    @staticmethod
    def _require_positive_int(
        data: Mapping[str, Any],
        field: str,
    ) -> int:
        """Read a required positive integer field."""
        if field not in data:
            raise RuntimeError(
                f"Massive response is missing '{field}'"
            )

        try:
            value = int(
                data[field]
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise RuntimeError(
                f"Massive response field "
                f"'{field}' is invalid"
            ) from exc

        if value <= 0:
            raise RuntimeError(
                f"Massive response field '{field}' "
                "must be greater than zero"
            )

        return value