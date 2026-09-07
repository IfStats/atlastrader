from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime

from packages.core.models import Quote
from packages.market_data.base import MarketDataProvider
from packages.market_data.comparison import (
    MarketDataComparator,
    MarketDataComparisonStatus,
)
from packages.market_data.observations import (
    MarketPriceObservation,
    ObservationalMarketDataProvider,
)
from packages.market_data.quality import (
    MarketDataQualityDecision,
    MarketDataQualityPolicy,
)


class MarketDataQualityService:
    """Build market-data quality decisions from multiple providers."""

    def __init__(
        self,
        *,
        authoritative_source: str,
        authoritative_provider: MarketDataProvider,
        reference_quote_providers: (
            Mapping[str, MarketDataProvider] | None
        ) = None,
        observational_providers: (
            Mapping[str, ObservationalMarketDataProvider] | None
        ) = None,
        comparator: MarketDataComparator | None = None,
        policy: MarketDataQualityPolicy | None = None,
    ) -> None:
        normalized_authoritative_source = (
            self._normalize_source(
                authoritative_source
            )
        )

        seen_sources = {
            normalized_authoritative_source.casefold()
        }

        normalized_quote_providers: dict[
            str,
            MarketDataProvider,
        ] = {}

        for source, quote_provider in (
            reference_quote_providers or {}
        ).items():
            normalized_source = (
                self._normalize_source(source)
            )

            self._register_source(
                normalized_source,
                seen_sources,
            )

            normalized_quote_providers[
                normalized_source
            ] = quote_provider

        normalized_observational_providers: dict[
            str,
            ObservationalMarketDataProvider,
        ] = {}

        for source, observational_provider in (
            observational_providers or {}
        ).items():
            normalized_source = (
                self._normalize_source(source)
            )

            self._register_source(
                normalized_source,
                seen_sources,
            )

            normalized_observational_providers[
                normalized_source
            ] = observational_provider

        self.authoritative_source = (
            normalized_authoritative_source
        )
        self.authoritative_provider = (
            authoritative_provider
        )

        self.reference_quote_providers = (
            normalized_quote_providers
        )
        self.observational_providers = (
            normalized_observational_providers
        )

        self.comparator = (
            comparator
            or MarketDataComparator()
        )
        self.policy = (
            policy
            or MarketDataQualityPolicy()
        )

    async def get_quality_decision(
        self,
        symbol: str,
        *,
        now: datetime | None = None,
    ) -> MarketDataQualityDecision:
        """Return the current multi-source market-data quality decision."""
        normalized_symbol = (
            self._normalize_symbol(symbol)
        )

        authoritative_quote = (
            await self.authoritative_provider.get_quote(
                normalized_symbol
            )
        )

        reference_quotes, quote_failures = (
            await self._get_reference_quotes(
                normalized_symbol
            )
        )

        observations, observation_failures = (
            await self._get_observations(
                normalized_symbol
            )
        )

        comparison_time = (
            now
            if now is not None
            else datetime.now(UTC)
        )

        comparison = self.comparator.compare(
            authoritative_source=(
                self.authoritative_source
            ),
            authoritative_quote=(
                authoritative_quote
            ),
            reference_quotes=reference_quotes,
            observations=observations,
            now=comparison_time,
        )

        failure_reasons = [
            *quote_failures,
            *observation_failures,
        ]

        if failure_reasons:
            updated_status = comparison.status

            if (
                updated_status
                is MarketDataComparisonStatus.HEALTHY
            ):
                updated_status = (
                    MarketDataComparisonStatus.DEGRADED
                )

            comparison = comparison.model_copy(
                update={
                    "status": updated_status,
                    "reasons": [
                        *comparison.reasons,
                        *failure_reasons,
                    ],
                }
            )

        return self.policy.evaluate(
            comparison
        )

    async def _get_reference_quotes(
        self,
        symbol: str,
    ) -> tuple[
        dict[str, Quote],
        list[str],
    ]:
        """Fetch secondary bid/ask quotes concurrently."""
        provider_items = list(
            self.reference_quote_providers.items()
        )

        if not provider_items:
            return {}, []

        results = await asyncio.gather(
            *[
                provider.get_quote(symbol)
                for _, provider in provider_items
            ],
            return_exceptions=True,
        )

        quotes: dict[str, Quote] = {}
        failures: list[str] = []

        for index, result in enumerate(results):
            source = provider_items[index][0]

            if isinstance(
                result,
                asyncio.CancelledError,
            ):
                raise result

            if isinstance(
                result,
                BaseException,
            ):
                failures.append(
                    f"reference_unavailable:{source}"
                )
                continue

            quotes[source] = result

        return quotes, failures

    async def _get_observations(
        self,
        symbol: str,
    ) -> tuple[
        list[MarketPriceObservation],
        list[str],
    ]:
        """Fetch observational midpoint sources concurrently."""
        provider_items = list(
            self.observational_providers.items()
        )

        if not provider_items:
            return [], []

        results = await asyncio.gather(
            *[
                provider.get_observation(
                    symbol
                )
                for _, provider in provider_items
            ],
            return_exceptions=True,
        )

        observations: list[
            MarketPriceObservation
        ] = []

        failures: list[str] = []

        for index, result in enumerate(results):
            configured_source = (
                provider_items[index][0]
            )

            if isinstance(
                result,
                asyncio.CancelledError,
            ):
                raise result

            if isinstance(
                result,
                BaseException,
            ):
                failures.append(
                    "reference_unavailable:"
                    f"{configured_source}"
                )
                continue

            if (
                result.source.casefold()
                != configured_source.casefold()
            ):
                raise ValueError(
                    "Observational provider source "
                    f"'{result.source}' does not match "
                    "configured source "
                    f"'{configured_source}'"
                )

            observations.append(
                result
            )

        return observations, failures

    @staticmethod
    def _normalize_symbol(
        symbol: str,
    ) -> str:
        """Normalize and validate the requested symbol."""
        normalized = (
            symbol.strip().upper()
        )

        if not normalized:
            raise ValueError(
                "symbol must not be empty"
            )

        return normalized

    @staticmethod
    def _normalize_source(
        source: str,
    ) -> str:
        """Normalize and validate a provider source name."""
        normalized = source.strip()

        if not normalized:
            raise ValueError(
                "source must not be empty"
            )

        return normalized

    @staticmethod
    def _register_source(
        source: str,
        seen_sources: set[str],
    ) -> None:
        """Reject duplicate configured provider identities."""
        key = source.casefold()

        if key in seen_sources:
            raise ValueError(
                "Duplicate market-data source: "
                f"{source}"
            )

        seen_sources.add(key)