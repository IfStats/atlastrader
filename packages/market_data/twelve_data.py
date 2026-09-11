from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar

from packages.core.enums import Timeframe
from packages.core.models import Candle
from packages.market_data.http import MarketDataHTTPTransport
from packages.market_data.observations import (
    MarketPriceObservation,
    ObservationalMarketDataProvider,
    PriceObservationType,
)


class TwelveDataObservationalProvider(
    ObservationalMarketDataProvider
):
    """Observational Twelve Data adapter for forex and metal pairs."""

    _INTERVAL_MAP: ClassVar[dict[Timeframe, str]] = {
        Timeframe.M1: "1min",
        Timeframe.M5: "5min",
        Timeframe.M15: "15min",
        Timeframe.M30: "30min",
        Timeframe.H1: "1h",
        Timeframe.H4: "4h",
        Timeframe.D1: "1day",
    }

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.twelvedata.com",
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
                "Authorization": f"apikey {normalized_api_key}",
            },
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
        )

        self._owns_transport = transport is None
        self._connected = False

    async def connect(self) -> None:
        """Start the owned HTTP transport."""
        if self._connected:
            return

        if self._owns_transport:
            await self._transport.start()

        self._connected = True

    async def disconnect(self) -> None:
        """Close the owned HTTP transport."""
        if not self._connected:
            return

        if self._owns_transport:
            await self._transport.close()

        self._connected = False

    async def get_observation(
        self,
        symbol: str,
    ) -> MarketPriceObservation:
        """Return the latest live midpoint observation."""
        self._require_connection()

        provider_symbol, canonical_symbol = (
            self._parse_pair_symbol(symbol)
        )

        payload = self._require_mapping(
            await self._transport.get_json(
                "/price",
                params={
                    "symbol": provider_symbol,
                },
            ),
            context="price response",
        )

        self._raise_for_provider_error(payload)

        price = self._require_positive_decimal(
            payload,
            "price",
        )

        return MarketPriceObservation(
            symbol=canonical_symbol,
            price=price,
            timestamp=datetime.now(UTC),
            source="Twelve Data",
            price_type=PriceObservationType.MID,
        )

    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        """Return historical observational OHLC candles."""
        self._require_connection()

        start_utc = self._normalize_datetime(start)
        end_utc = self._normalize_datetime(end)

        if start_utc >= end_utc:
            raise ValueError(
                "start must be earlier than end"
            )

        provider_symbol, canonical_symbol = (
            self._parse_pair_symbol(symbol)
        )

        interval = self._INTERVAL_MAP[timeframe]

        payload = self._require_mapping(
            await self._transport.get_json(
                "/time_series",
                params={
                    "symbol": provider_symbol,
                    "interval": interval,
                    "timezone": "UTC",
                    "start_date": self._format_datetime(
                        start_utc
                    ),
                    "end_date": self._format_datetime(
                        end_utc
                    ),
                    "order": "asc",
                },
            ),
            context="time-series response",
        )

        self._raise_for_provider_error(payload)

        raw_values = payload.get(
            "values",
            [],
        )

        if raw_values is None:
            return []

        if not isinstance(raw_values, list):
            raise TypeError(
                "Twelve Data time-series response "
                "'values' must be a list"
            )

        candles: list[Candle] = []

        for raw_value in raw_values:
            value = self._require_mapping(
                raw_value,
                context="time-series value",
            )

            candles.append(
                Candle(
                    symbol=canonical_symbol,
                    timeframe=timeframe,
                    timestamp=self._parse_datetime(
                        value.get("datetime")
                    ),
                    open=self._require_positive_decimal(
                        value,
                        "open",
                    ),
                    high=self._require_positive_decimal(
                        value,
                        "high",
                    ),
                    low=self._require_positive_decimal(
                        value,
                        "low",
                    ),
                    close=self._require_positive_decimal(
                        value,
                        "close",
                    ),
                    volume=self._optional_nonnegative_decimal(
                        value,
                        "volume",
                    ),
                )
            )

        return sorted(
            candles,
            key=lambda candle: candle.timestamp,
        )

    def _require_connection(self) -> None:
        """Raise when the provider has not been connected."""
        if not self._connected:
            raise RuntimeError(
                "Observational market-data provider "
                "is not connected"
            )

    @staticmethod
    def _parse_pair_symbol(
        symbol: str,
    ) -> tuple[str, str]:
        """Normalize a six-letter forex or metal pair."""
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
                "Twelve Data pair symbols must contain "
                "two three-letter codes"
            )

        provider_symbol = (
            f"{normalized[:3]}/{normalized[3:]}"
        )

        return provider_symbol, normalized

    @staticmethod
    def _normalize_datetime(
        value: datetime,
    ) -> datetime:
        """Return a UTC-aware datetime."""
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)

    @staticmethod
    def _format_datetime(
        value: datetime,
    ) -> str:
        """Format a UTC datetime for Twelve Data."""
        return value.strftime(
            "%Y-%m-%dT%H:%M:%S"
        )

    @staticmethod
    def _parse_datetime(
        value: Any,
    ) -> datetime:
        """Parse a Twelve Data datetime as UTC."""
        if not isinstance(value, str):
            raise TypeError(
                "Twelve Data datetime must be a string"
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Twelve Data datetime must not be empty"
            )

        try:
            parsed = datetime.fromisoformat(
                normalized
            )
        except ValueError as exc:
            raise ValueError(
                "Twelve Data datetime is invalid"
            ) from exc

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)

        return parsed.astimezone(UTC)

    @staticmethod
    def _raise_for_provider_error(
        payload: Mapping[str, Any],
    ) -> None:
        """Raise when Twelve Data returns an API error payload."""
        if payload.get("status") != "error":
            return

        message = payload.get(
            "message",
            "Unknown Twelve Data error",
        )

        raise RuntimeError(
            f"Twelve Data API error: {message}"
        )

    @staticmethod
    def _require_mapping(
        value: Any,
        *,
        context: str,
    ) -> Mapping[str, Any]:
        """Validate that a payload component is an object."""
        if not isinstance(value, Mapping):
            raise TypeError(
                f"Twelve Data {context} must be an object"
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
                f"Twelve Data response is missing "
                f"'{field}'"
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
                f"Twelve Data response field "
                f"'{field}' is invalid"
            ) from exc

        if value <= 0:
            raise RuntimeError(
                f"Twelve Data response field "
                f"'{field}' must be greater than zero"
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

        if raw_value is None:
            return Decimal(0)

        try:
            value = Decimal(
                str(raw_value)
            )
        except (
            InvalidOperation,
            ValueError,
        ) as exc:
            raise RuntimeError(
                f"Twelve Data response field "
                f"'{field}' is invalid"
            ) from exc

        if value < 0:
            raise RuntimeError(
                f"Twelve Data response field "
                f"'{field}' must not be negative"
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
                f"Twelve Data response is missing "
                f"'{field}'"
            )

        try:
            value = int(data[field])
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise RuntimeError(
                f"Twelve Data response field "
                f"'{field}' is invalid"
            ) from exc

        if value <= 0:
            raise RuntimeError(
                f"Twelve Data response field "
                f"'{field}' must be greater than zero"
            )

        return value