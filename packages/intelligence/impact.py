from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

from packages.core.enums import SignalDirection
from packages.core.intelligence import MarketEvent
from packages.intelligence.normalizer import NormalizedIntelligence


class SymbolImpact(BaseModel):
    symbol: str
    direction: SignalDirection
    directional_score: float = Field(ge=-1.0, le=1.0)
    impact_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    news_count: int = Field(ge=0)
    rationale: list[str] = Field(default_factory=list)


class MarketImpactContext(BaseModel):
    generated_at: datetime
    impacts: list[SymbolImpact] = Field(default_factory=list)
    event_risk_score: float = Field(ge=0.0, le=1.0)
    high_impact_event_count: int = Field(ge=0)
    rationale: list[str] = Field(default_factory=list)


class MarketImpactEngine:
    """Convert normalized intelligence into deterministic market-impact context."""

    def __init__(
        self,
        *,
        intelligence_max_age: timedelta = timedelta(hours=24),
        decay_floor: float = 0.10,
    ) -> None:
        if intelligence_max_age <= timedelta(0):
            raise ValueError("intelligence_max_age must be greater than zero")

        if not 0.0 <= decay_floor <= 1.0:
            raise ValueError("decay_floor must be between 0 and 1")

        self.intelligence_max_age = intelligence_max_age
        self.decay_floor = decay_floor

    def assess(
        self,
        *,
        intelligence: list[NormalizedIntelligence],
        events: list[MarketEvent] | None = None,
        now: datetime | None = None,
    ) -> MarketImpactContext:
        reference_time = now or datetime.now(UTC)

        impacts_by_symbol: dict[str, list[tuple[float, float, float, str]]] = {}

        for item in intelligence:
            published_at = self._get_published_at(item)

            age = reference_time - published_at
            age = max(age, timedelta(0))

            if age > self.intelligence_max_age:
                continue

            decay = self._time_decay(age)

            for assessment in item.assessments:
                directional_value = self._directional_value(
                    assessment.direction
                )

                weighted_impact = assessment.impact_score * decay
                weighted_confidence = assessment.confidence * decay
                weighted_direction = directional_value * weighted_impact

                impacts_by_symbol.setdefault(assessment.symbol, []).append(
                    (
                        weighted_direction,
                        weighted_impact,
                        weighted_confidence,
                        item.headline,
                    )
                )

        impacts = [
            self._build_symbol_impact(symbol, values)
            for symbol, values in sorted(impacts_by_symbol.items())
        ]

        event_risk_score, high_impact_event_count = self._calculate_event_risk(
            events or [],
            now=reference_time,
        )

        rationale = [
            f"symbols_assessed={len(impacts)}",
            f"high_impact_events={high_impact_event_count}",
            f"event_risk_score={event_risk_score:.3f}",
        ]

        return MarketImpactContext(
            generated_at=reference_time,
            impacts=impacts,
            event_risk_score=event_risk_score,
            high_impact_event_count=high_impact_event_count,
            rationale=rationale,
        )

    def _build_symbol_impact(
        self,
        symbol: str,
        values: list[tuple[float, float, float, str]],
    ) -> SymbolImpact:
        total_impact = sum(value[1] for value in values)

        if total_impact == 0.0:
            directional_score = 0.0
        else:
            directional_score = sum(
                value[0] for value in values
            ) / total_impact

        directional_score = max(-1.0, min(1.0, directional_score))

        impact_score = min(
            1.0,
            sum(value[1] for value in values),
        )

        confidence_denominator = sum(
            value[1] for value in values
        )

        if confidence_denominator == 0.0:
            confidence = 0.0
        else:
            confidence = sum(
                value[1] * value[2]
                for value in values
            ) / confidence_denominator

        direction = self._score_to_direction(directional_score)

        rationale = [
            f"news_count={len(values)}",
            f"directional_score={directional_score:.3f}",
            f"impact_score={impact_score:.3f}",
            f"confidence={confidence:.3f}",
        ]

        return SymbolImpact(
            symbol=symbol,
            direction=direction,
            directional_score=directional_score,
            impact_score=impact_score,
            confidence=confidence,
            news_count=len(values),
            rationale=rationale,
        )

    def _calculate_event_risk(
        self,
        events: list[MarketEvent],
        *,
        now: datetime,
    ) -> tuple[float, int]:
        active_events = [
            event
            for event in events
            if event.is_confirmed
            and event.scheduled_at >= now
            and event.scheduled_at
            <= now + self.intelligence_max_age
        ]

        high_impact_events = [
            event
            for event in active_events
            if event.importance >= 0.70
        ]

        if not active_events:
            return 0.0, 0

        risk = max(
            event.importance
            for event in active_events
        )

        return min(1.0, risk), len(high_impact_events)

    def _time_decay(self, age: timedelta) -> float:
        elapsed_seconds = max(0.0, age.total_seconds())
        maximum_seconds = self.intelligence_max_age.total_seconds()

        if maximum_seconds == 0:
            return self.decay_floor

        freshness = max(
            0.0,
            1.0 - elapsed_seconds / maximum_seconds,
        )

        return self.decay_floor + (
            (1.0 - self.decay_floor) * freshness
        )

    @staticmethod
    def _get_published_at(
        intelligence: NormalizedIntelligence,
    ) -> datetime:
        return intelligence.published_at

    @staticmethod
    def _directional_value(direction: SignalDirection) -> float:
        if direction is SignalDirection.LONG:
            return 1.0

        if direction is SignalDirection.SHORT:
            return -1.0

        return 0.0

    @staticmethod
    def _score_to_direction(score: float) -> SignalDirection:
        if score > 0:
            return SignalDirection.LONG

        if score < 0:
            return SignalDirection.SHORT

        return SignalDirection.FLAT