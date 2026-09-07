from __future__ import annotations

from pydantic import BaseModel, Field

from packages.market_data.comparison import (
    MarketDataComparison,
    MarketDataComparisonStatus,
)


class MarketDataQualityDecision(BaseModel):
    """Policy decision derived from multi-source market-data quality."""

    trading_permitted: bool
    confidence_multiplier: float = Field(ge=0.0, le=1.0)
    status: MarketDataComparisonStatus
    reasons: list[str] = Field(default_factory=list)


class MarketDataQualityPolicy:
    """Translate market-data comparison health into pre-trade policy."""

    def __init__(
        self,
        *,
        degraded_confidence_multiplier: float = 0.75,
        block_degraded: bool = False,
    ) -> None:
        if not 0.0 <= degraded_confidence_multiplier <= 1.0:
            raise ValueError(
                "degraded_confidence_multiplier must be "
                "between 0 and 1"
            )

        self.degraded_confidence_multiplier = (
            degraded_confidence_multiplier
        )
        self.block_degraded = block_degraded

    def evaluate(
        self,
        comparison: MarketDataComparison,
    ) -> MarketDataQualityDecision:
        """Evaluate whether current market-data quality permits trading."""

        if (
            comparison.status
            is MarketDataComparisonStatus.ANOMALOUS
        ):
            return MarketDataQualityDecision(
                trading_permitted=False,
                confidence_multiplier=0.0,
                status=comparison.status,
                reasons=self._build_reasons(
                    comparison,
                    "market_data_anomalous",
                ),
            )

        if (
            comparison.status
            is MarketDataComparisonStatus.DEGRADED
        ):
            if self.block_degraded:
                return MarketDataQualityDecision(
                    trading_permitted=False,
                    confidence_multiplier=0.0,
                    status=comparison.status,
                    reasons=self._build_reasons(
                        comparison,
                        "market_data_degraded_blocked",
                    ),
                )

            return MarketDataQualityDecision(
                trading_permitted=True,
                confidence_multiplier=(
                    self.degraded_confidence_multiplier
                ),
                status=comparison.status,
                reasons=self._build_reasons(
                    comparison,
                    "market_data_degraded",
                ),
            )

        return MarketDataQualityDecision(
            trading_permitted=True,
            confidence_multiplier=1.0,
            status=comparison.status,
            reasons=[],
        )

    @staticmethod
    def _build_reasons(
        comparison: MarketDataComparison,
        policy_reason: str,
    ) -> list[str]:
        """Combine policy and comparator reason codes."""
        return [
            policy_reason,
            *comparison.reasons,
        ]