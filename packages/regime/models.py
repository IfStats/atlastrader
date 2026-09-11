from decimal import Decimal
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from packages.performance.models import (
    PerformanceSummary,
)


class TrendRegime(StrEnum):
    """Deterministic trend-state classification."""

    STRONG_UPTREND = "strong_uptrend"
    UPTREND = "uptrend"
    NEUTRAL = "neutral"
    DOWNTREND = "downtrend"
    STRONG_DOWNTREND = "strong_downtrend"


class VolatilityRegime(StrEnum):
    """Deterministic volatility-state classification."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class MomentumRelationship(StrEnum):
    """Relationship between directional trade intent and momentum."""

    ALIGNED = "aligned"
    WEAK = "weak"
    CONFLICTING = "conflicting"


class MarketRegime(BaseModel):
    """Immutable deterministic market-regime label."""

    model_config = ConfigDict(
        frozen=True
    )

    trend: TrendRegime
    volatility: VolatilityRegime
    momentum: MomentumRelationship

    @property
    def key(self) -> str:
        """Return stable compound regime identifier."""
        return (
            f"{self.trend.value}|"
            f"{self.volatility.value}|"
            f"{self.momentum.value}"
        )


class RegimePerformanceSummary(BaseModel):
    """Performance partitioned by deterministic market regime."""

    model_config = ConfigDict(
        frozen=True
    )

    overall: PerformanceSummary

    by_regime: dict[
        str,
        PerformanceSummary,
    ] = Field(
        default_factory=dict
    )


class RegimeQuality(StrEnum):
    """Deterministic quality classification for a regime."""

    STRONG = "strong"
    POSITIVE = "positive"
    INCONCLUSIVE = "inconclusive"
    NEGATIVE = "negative"
    POOR = "poor"


class RegimePattern(BaseModel):
    """Evaluated performance pattern for one market regime."""

    model_config = ConfigDict(
        frozen=True
    )

    regime_key: str

    sample_size: int = Field(
        ge=0
    )

    performance: PerformanceSummary

    quality: RegimeQuality

    expectancy: Decimal
    win_rate: Decimal

    profit_factor: Decimal | None = None
    payoff_ratio: Decimal | None = None

    sufficient_sample: bool

class StrategyRegimePattern(BaseModel):
    """Performance pattern for one strategy inside one market regime."""

    model_config = ConfigDict(
        frozen=True
    )

    strategy: str
    regime_key: str

    sample_size: int = Field(
        ge=0
    )

    performance: PerformanceSummary

    quality: RegimeQuality

    sufficient_sample: bool

    @property
    def key(self) -> str:
        """Return stable strategy-regime identifier."""
        return (
            f"{self.strategy}|"
            f"{self.regime_key}"
       )

class PromotionEligibility(BaseModel):
    """Deterministic promotion decision for a strategy-regime pattern."""

    model_config = ConfigDict(
        frozen=True
    )

    pattern_key: str

    eligible: bool

    sample_size: int = Field(
        ge=0
    )

    quality: RegimeQuality

    expectancy: Decimal
    win_rate: Decimal

    profit_factor: Decimal | None = None
    payoff_ratio: Decimal | None = None

    rejection_reasons: list[str] = Field(
        default_factory=list
    )    