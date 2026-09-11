from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from packages.core.models import Quote
from packages.market_data.observations import (
    MarketPriceObservation,
)


class MarketDataComparisonStatus(StrEnum):
    """Overall health classification for a multi-source comparison."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ANOMALOUS = "anomalous"


class SourcePriceComparison(BaseModel):
    """Comparison of one market-data source against execution truth."""

    source: str
    price: Decimal = Field(gt=0)
    timestamp: datetime
    age_seconds: float = Field(ge=0)
    deviation_bps: Decimal = Field(ge=0)
    is_authoritative: bool = False
    is_stale: bool = False
    is_future: bool = False
    is_deviant: bool = False

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        """Normalize and validate the source name."""
        normalized = value.strip()

        if not normalized:
            raise ValueError("source must not be empty")

        return normalized

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        """Require timezone-aware timestamps and normalize to UTC."""
        if value.tzinfo is None:
            raise ValueError(
                "timestamp must be timezone-aware"
            )

        return value.astimezone(UTC)


class MarketDataComparison(BaseModel):
    """Normalized multi-source market-data comparison result."""

    symbol: str
    authoritative_source: str
    authoritative_price: Decimal = Field(gt=0)

    consensus_price: Decimal | None = Field(
        default=None,
        gt=0,
    )
    consensus_deviation_bps: Decimal | None = Field(
        default=None,
        ge=0,
    )

    generated_at: datetime
    source_count: int = Field(ge=1)
    fresh_source_count: int = Field(ge=0)

    status: MarketDataComparisonStatus
    sources: list[SourcePriceComparison]
    reasons: list[str] = Field(default_factory=list)


class MarketDataComparator:
    """Compare external market observations against execution truth."""

    def __init__(
        self,
        *,
        max_age_seconds: float = 5.0,
        max_deviation_bps: Decimal = Decimal(5),
        min_fresh_sources: int = 2,
    ) -> None:
        if max_age_seconds <= 0:
            raise ValueError(
                "max_age_seconds must be greater than zero"
            )

        if max_deviation_bps <= 0:
            raise ValueError(
                "max_deviation_bps must be greater than zero"
            )

        if min_fresh_sources < 1:
            raise ValueError(
                "min_fresh_sources must be at least 1"
            )

        self.max_age_seconds = max_age_seconds
        self.max_deviation_bps = max_deviation_bps
        self.min_fresh_sources = min_fresh_sources

    def compare(
        self,
        *,
        authoritative_source: str,
        authoritative_quote: Quote,
        reference_quotes: Mapping[str, Quote] | None = None,
        observations: list[MarketPriceObservation] | None = None,
        now: datetime | None = None,
    ) -> MarketDataComparison:
        """Compare reference sources with the authoritative quote."""
        comparison_time = self._normalize_comparison_time(
            now or datetime.now(UTC)
        )

        normalized_authoritative_source = (
            self._normalize_source(
                authoritative_source
            )
        )

        symbol = self._normalize_symbol(
            authoritative_quote.symbol
        )

        authoritative_timestamp = (
            self._normalize_timestamp(
                authoritative_quote.timestamp
            )
        )

        authoritative_price = (
            authoritative_quote.mid_price
        )

        entries: list[
            tuple[
                str,
                Decimal,
                datetime,
                bool,
            ]
        ] = [
            (
                normalized_authoritative_source,
                authoritative_price,
                authoritative_timestamp,
                True,
            )
        ]

        seen_sources = {
            normalized_authoritative_source.casefold()
        }

        for source, quote in (
            reference_quotes or {}
        ).items():
            normalized_source = self._normalize_source(
                source
            )

            self._register_source(
                normalized_source,
                seen_sources,
            )

            self._require_matching_symbol(
                symbol,
                quote.symbol,
            )

            entries.append(
                (
                    normalized_source,
                    quote.mid_price,
                    self._normalize_timestamp(
                        quote.timestamp
                    ),
                    False,
                )
            )

        for observation in observations or []:
            normalized_source = self._normalize_source(
                observation.source
            )

            self._register_source(
                normalized_source,
                seen_sources,
            )

            self._require_matching_symbol(
                symbol,
                observation.symbol,
            )

            entries.append(
                (
                    normalized_source,
                    observation.price,
                    self._normalize_timestamp(
                        observation.timestamp
                    ),
                    False,
                )
            )

        comparisons = [
            self._build_source_comparison(
                source=source,
                price=price,
                timestamp=timestamp,
                authoritative_price=authoritative_price,
                is_authoritative=is_authoritative,
                comparison_time=comparison_time,
            )
            for (
                source,
                price,
                timestamp,
                is_authoritative,
            ) in entries
        ]

        fresh_prices = [
            comparison.price
            for comparison in comparisons
            if (
                not comparison.is_stale
                and not comparison.is_future
            )
        ]

        consensus_price = self._median(
            fresh_prices
        )

        consensus_deviation_bps = (
            None
            if consensus_price is None
            else self._deviation_bps(
                consensus_price,
                authoritative_price,
            )
        )

        reasons: list[str] = []
        anomaly_detected = False
        degraded_detected = False

        authoritative_comparison = comparisons[0]

        if authoritative_comparison.is_future:
            reasons.append(
                "authoritative_source_future"
            )
            anomaly_detected = True
        elif authoritative_comparison.is_stale:
            reasons.append(
                "authoritative_source_stale"
            )
            anomaly_detected = True

        for comparison in comparisons[1:]:
            if comparison.is_future:
                reasons.append(
                    f"future_reference:{comparison.source}"
                )
                anomaly_detected = True
            elif comparison.is_stale:
                reasons.append(
                    f"stale_reference:{comparison.source}"
                )
                degraded_detected = True

            if comparison.is_deviant:
                reasons.append(
                    f"reference_deviation:{comparison.source}"
                )
                anomaly_detected = True

        fresh_source_count = len(
            fresh_prices
        )

        if (
            fresh_source_count
            < self.min_fresh_sources
        ):
            reasons.append(
                "insufficient_fresh_sources"
            )
            degraded_detected = True

        if anomaly_detected:
            status = (
                MarketDataComparisonStatus.ANOMALOUS
            )
        elif degraded_detected:
            status = (
                MarketDataComparisonStatus.DEGRADED
            )
        else:
            status = (
                MarketDataComparisonStatus.HEALTHY
            )

        return MarketDataComparison(
            symbol=symbol,
            authoritative_source=(
                normalized_authoritative_source
            ),
            authoritative_price=(
                authoritative_price
            ),
            consensus_price=consensus_price,
            consensus_deviation_bps=(
                consensus_deviation_bps
            ),
            generated_at=comparison_time,
            source_count=len(comparisons),
            fresh_source_count=(
                fresh_source_count
            ),
            status=status,
            sources=comparisons,
            reasons=reasons,
        )

    def _build_source_comparison(
        self,
        *,
        source: str,
        price: Decimal,
        timestamp: datetime,
        authoritative_price: Decimal,
        is_authoritative: bool,
        comparison_time: datetime,
    ) -> SourcePriceComparison:
        """Build comparison metrics for one source."""
        raw_age_seconds = (
            comparison_time
            - timestamp
        ).total_seconds()

        is_future = raw_age_seconds < 0

        age_seconds = max(
            0.0,
            raw_age_seconds,
        )

        deviation_bps = self._deviation_bps(
            price,
            authoritative_price,
        )

        is_stale = (
            not is_future
            and age_seconds > self.max_age_seconds
        )

        is_deviant = (
            not is_authoritative
            and not is_stale
            and not is_future
            and deviation_bps
            > self.max_deviation_bps
        )

        return SourcePriceComparison(
            source=source,
            price=price,
            timestamp=timestamp,
            age_seconds=age_seconds,
            deviation_bps=deviation_bps,
            is_authoritative=is_authoritative,
            is_stale=is_stale,
            is_future=is_future,
            is_deviant=is_deviant,
        )

    @staticmethod
    def _deviation_bps(
        price: Decimal,
        authoritative_price: Decimal,
    ) -> Decimal:
        """Return absolute deviation from execution truth in basis points."""
        return (
            abs(
                price
                - authoritative_price
            )
            / authoritative_price
            * Decimal(10000)
        )

    @staticmethod
    def _median(
        values: list[Decimal],
    ) -> Decimal | None:
        """Return the median of the supplied prices."""
        if not values:
            return None

        ordered = sorted(values)
        midpoint = len(ordered) // 2

        if len(ordered) % 2:
            return ordered[midpoint]

        return (
            ordered[midpoint - 1]
            + ordered[midpoint]
        ) / Decimal(2)

    @staticmethod
    def _normalize_source(
        source: str,
    ) -> str:
        """Normalize and validate a source name."""
        normalized = source.strip()

        if not normalized:
            raise ValueError(
                "source must not be empty"
            )

        return normalized

    @staticmethod
    def _normalize_symbol(
        symbol: str,
    ) -> str:
        """Normalize and validate a canonical symbol."""
        normalized = (
            symbol.strip().upper()
        )

        if not normalized:
            raise ValueError(
                "symbol must not be empty"
            )

        return normalized

    @staticmethod
    def _normalize_timestamp(
        timestamp: datetime,
    ) -> datetime:
        """Normalize a provider timestamp to UTC."""
        if timestamp.tzinfo is None:
            raise ValueError(
                "market-data timestamps must "
                "be timezone-aware"
            )

        return timestamp.astimezone(UTC)

    @staticmethod
    def _normalize_comparison_time(
        value: datetime,
    ) -> datetime:
        """Normalize the comparison time to UTC."""
        if value.tzinfo is None:
            raise ValueError(
                "comparison time must "
                "be timezone-aware"
            )

        return value.astimezone(UTC)

    @classmethod
    def _require_matching_symbol(
        cls,
        expected: str,
        actual: str,
    ) -> None:
        """Reject market data belonging to another instrument."""
        normalized_actual = (
            cls._normalize_symbol(actual)
        )

        if normalized_actual != expected:
            raise ValueError(
                "Market-data source symbol "
                f"'{normalized_actual}' does not match "
                f"authoritative symbol '{expected}'"
            )

    @staticmethod
    def _register_source(
        source: str,
        seen_sources: set[str],
    ) -> None:
        """Reject duplicate provider names."""
        key = source.casefold()

        if key in seen_sources:
            raise ValueError(
                f"Duplicate market-data source: {source}"
            )

        seen_sources.add(key)