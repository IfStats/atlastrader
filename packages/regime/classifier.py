from packages.core.enums import (
    SignalDirection,
)
from packages.learning.models import (
    LearningRecord,
)
from packages.regime.models import (
    MarketRegime,
    MomentumRelationship,
    TrendRegime,
    VolatilityRegime,
)


class MarketRegimeClassifier:
    """Classify completed-trade records into deterministic market regimes."""

    STRONG_TREND_THRESHOLD = 0.60
    TREND_THRESHOLD = 0.20

    LOW_VOLATILITY_THRESHOLD = 0.33
    HIGH_VOLATILITY_THRESHOLD = 0.67

    STRONG_MOMENTUM_THRESHOLD = 0.20

    def classify(
        self,
        record: LearningRecord,
    ) -> MarketRegime:
        """Return deterministic regime classification for a learning record."""
        return MarketRegime(
            trend=self.classify_trend(
                record.trend_score
            ),
            volatility=self.classify_volatility(
                record.volatility_score
            ),
            momentum=self.classify_momentum(
                direction=record.direction,
                momentum_score=(
                    record.momentum_score
                ),
            ),
        )

    def classify_trend(
        self,
        trend_score: float,
    ) -> TrendRegime:
        """Classify normalized trend score."""
        if (
            trend_score
            >= self.STRONG_TREND_THRESHOLD
        ):
            return (
                TrendRegime.STRONG_UPTREND
            )

        if (
            trend_score
            >= self.TREND_THRESHOLD
        ):
            return TrendRegime.UPTREND

        if (
            trend_score
            > -self.TREND_THRESHOLD
        ):
            return TrendRegime.NEUTRAL

        if (
            trend_score
            > -self.STRONG_TREND_THRESHOLD
        ):
            return TrendRegime.DOWNTREND

        return (
            TrendRegime.STRONG_DOWNTREND
        )

    def classify_volatility(
        self,
        volatility_score: float,
    ) -> VolatilityRegime:
        """Classify normalized volatility score."""
        if (
            volatility_score
            < self.LOW_VOLATILITY_THRESHOLD
        ):
            return VolatilityRegime.LOW

        if (
            volatility_score
            < self.HIGH_VOLATILITY_THRESHOLD
        ):
            return VolatilityRegime.NORMAL

        return VolatilityRegime.HIGH

    def classify_momentum(
        self,
        *,
        direction: SignalDirection,
        momentum_score: float,
    ) -> MomentumRelationship:
        """Classify momentum relative to the trade direction."""
        threshold = (
            self.STRONG_MOMENTUM_THRESHOLD
        )

        if direction is SignalDirection.LONG:
            if momentum_score >= threshold:
                return (
                    MomentumRelationship.ALIGNED
                )

            if momentum_score <= -threshold:
                return (
                    MomentumRelationship.CONFLICTING
                )

            return MomentumRelationship.WEAK

        if direction is SignalDirection.SHORT:
            if momentum_score <= -threshold:
                return (
                    MomentumRelationship.ALIGNED
                )

            if momentum_score >= threshold:
                return (
                    MomentumRelationship.CONFLICTING
                )

            return MomentumRelationship.WEAK

        raise ValueError(
            "Market-regime classification "
            "requires a directional trade"
        )