from __future__ import annotations

import re

from pydantic import BaseModel, Field

from packages.core.enums import SignalDirection
from packages.core.intelligence import MarketNews


class ImpactAssessment(BaseModel):
    symbol: str
    direction: SignalDirection
    impact_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: list[str] = Field(default_factory=list)


class NormalizedIntelligence(BaseModel):
    source_id: str
    provider: str | None = None
    headline: str
    event_type: str
    symbols: list[str] = Field(default_factory=list)
    asset_classes: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)

    sentiment_score: float = Field(ge=-1.0, le=1.0)
    relevance_score: float = Field(ge=0.0, le=1.0)
    impact_score: float = Field(ge=0.0, le=1.0)

    assessments: list[ImpactAssessment] = Field(default_factory=list)


class IntelligenceNormalizer:
    """Deterministically normalize market intelligence for downstream engines."""

    _EVENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "monetary_policy",
            (
                "interest rate",
                "rate decision",
                "rate hike",
                "rate cut",
                "central bank",
                "federal reserve",
                "bank of england",
                "bank of japan",
                "fed",
                "ecb",
                "boe",
                "boj",
            ),
        ),
        (
            "inflation",
            (
                "consumer price index",
                "producer price index",
                "price pressures",
                "inflation",
                "cpi",
                "ppi",
            ),
        ),
        (
            "employment",
            (
                "jobs report",
                "jobless claims",
                "nonfarm payroll",
                "non-farm payroll",
                "wage growth",
                "employment",
                "unemployment",
                "payrolls",
            ),
        ),
        (
            "geopolitical",
            (
                "geopolitical",
                "airstrike",
                "ceasefire",
                "sanctions",
                "invasion",
                "conflict",
                "missile",
                "military",
                "tensions",
                "war",
            ),
        ),
        (
            "economic_growth",
            (
                "economic growth",
                "services activity",
                "manufacturing",
                "contraction",
                "expansion",
                "recession",
                "gdp",
                "pmi",
            ),
        ),
        (
            "commodity",
            (
                "natural gas",
                "commodity",
                "crude",
                "gold",
                "silver",
                "copper",
                "opec",
                "oil",
            ),
        ),
        (
            "financial_markets",
            (
                "treasury yields",
                "stock market",
                "bond yields",
                "market rally",
                "equities",
                "selloff",
                "sell-off",
                "stocks",
            ),
        ),
    )

    _POSITIVE_TERMS: tuple[str, ...] = (
        "beat",
        "beats",
        "strong",
        "stronger",
        "surge",
        "surges",
        "rally",
        "rallies",
        "rise",
        "rises",
        "higher",
        "growth",
        "improves",
        "improved",
        "bullish",
        "hawkish",
    )

    _NEGATIVE_TERMS: tuple[str, ...] = (
        "miss",
        "misses",
        "weak",
        "weaker",
        "fall",
        "falls",
        "decline",
        "declines",
        "lower",
        "recession",
        "crisis",
        "bearish",
        "dovish",
        "cuts",
        "cut",
    )

    _ENTITY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "Federal Reserve",
            ("fed", "federal reserve", "fomc"),
        ),
        (
            "European Central Bank",
            ("ecb", "european central bank"),
        ),
        (
            "Bank of England",
            ("boe", "bank of england"),
        ),
        (
            "Bank of Japan",
            ("boj", "bank of japan"),
        ),
        (
            "OPEC",
            ("opec",),
        ),
    )

    # Pre-compiled word-boundary regular expressions to prevent substring collisions
    _POS_PATTERN = re.compile(
        r"\b(" + "|".join(_POSITIVE_TERMS) + r")\b", re.IGNORECASE
    )
    _NEG_PATTERN = re.compile(
        r"\b(" + "|".join(_NEGATIVE_TERMS) + r")\b", re.IGNORECASE
    )

    def normalize(self, news: MarketNews) -> NormalizedIntelligence:
        headline = self._clean_text(news.headline)
        lowered = headline.lower()

        event_type = self._classify_event(lowered)
        entities = self._extract_entities(lowered)
        symbols = self._normalize_symbols(news.symbols)

        sentiment_score = self._calculate_sentiment(lowered)

        relevance_score = self._calculate_relevance(
            headline=lowered,
            symbols=symbols,
        )

        impact_score = self._calculate_impact(
            news=news,
            event_type=event_type,
            headline=lowered,
        )

        assessments = self._build_assessments(
            symbols=symbols,
            event_type=event_type,
            sentiment_score=sentiment_score,
            impact_score=impact_score,
            headline=lowered,
        )

        return NormalizedIntelligence(
            source_id=str(news.id),
            provider=news.provider,
            headline=headline,
            event_type=event_type,
            symbols=symbols,
            asset_classes=list(news.asset_classes),
            countries=list(news.countries),
            entities=entities,
            sentiment_score=sentiment_score,
            relevance_score=relevance_score,
            impact_score=impact_score,
            assessments=assessments,
        )

    @staticmethod
    def _clean_text(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @classmethod
    def _classify_event(cls, headline: str) -> str:
        for event_type, keywords in cls._EVENT_RULES:
            if any(kw in headline for kw in keywords):
                return event_type
        return "general_market"

    @classmethod
    def _extract_entities(cls, headline: str) -> list[str]:
        entities: list[str] = []
        for entity, keywords in cls._ENTITY_RULES:
            if any(
                re.search(r"\b" + re.escape(kw) + r"\b", headline)
                for kw in keywords
            ):
                entities.append(entity)
        return entities

    @classmethod
    def _calculate_sentiment(cls, headline: str) -> float:
        positive_hits = len(cls._POS_PATTERN.findall(headline))
        negative_hits = len(cls._NEG_PATTERN.findall(headline))

        if positive_hits == 0 and negative_hits == 0:
            return 0.0

        total = positive_hits + negative_hits
        score = (positive_hits - negative_hits) / total
        return max(-1.0, min(1.0, score))

    @staticmethod
    def _calculate_relevance(
        *,
        headline: str,
        symbols: list[str],
    ) -> float:
        if symbols:
            return 1.0

        market_keywords = {
            "market",
            "economy",
            "central bank",
            "interest rate",
            "inflation",
            "employment",
            "gdp",
            "oil",
            "gold",
        }
        if any(kw in headline for kw in market_keywords):
            return 0.75

        return 0.25

    @staticmethod
    def _calculate_impact(
        *,
        news: MarketNews,
        event_type: str,
        headline: str,
    ) -> float:
        raw_impact = float(getattr(news, "impact_score", 0.0))
        raw_relevance = float(getattr(news, "relevance_score", 0.0))

        base = max(raw_impact, raw_relevance * 0.75)

        high_impact_events = {
            "monetary_policy",
            "inflation",
            "employment",
            "geopolitical",
        }
        if event_type in high_impact_events:
            base += 0.15

        high_impact_triggers = (
            "emergency",
            "unexpected",
            "surprise",
            "crisis",
            "war",
            "sanctions",
        )
        if any(term in headline for term in high_impact_triggers):
            base += 0.10

        return max(0.0, min(1.0, base))

    def _build_assessments(
        self,
        *,
        symbols: list[str],
        event_type: str,
        sentiment_score: float,
        impact_score: float,
        headline: str,
    ) -> list[ImpactAssessment]:
        assessments: list[ImpactAssessment] = []

        for symbol in symbols:
            direction = self._infer_direction(
                symbol=symbol,
                event_type=event_type,
                sentiment_score=sentiment_score,
                headline=headline,
            )

            confidence = self._calculate_confidence(
                event_type=event_type,
                sentiment_score=sentiment_score,
                symbol=symbol,
            )

            rationale = [
                f"event_type={event_type}",
                f"sentiment_score={sentiment_score:.3f}",
            ]

            assessments.append(
                ImpactAssessment(
                    symbol=symbol,
                    direction=direction,
                    impact_score=impact_score,
                    confidence=confidence,
                    rationale=rationale,
                )
            )

        return assessments

    @staticmethod
    def _normalize_symbols(symbols: list[str]) -> list[str]:
        seen = set()
        normalized: list[str] = []

        for symbol in symbols:
            value = symbol.strip().upper()
            if value and value not in seen:
                seen.add(value)
                normalized.append(value)

        return normalized

    @staticmethod
    def _infer_direction(
        *,
        symbol: str,
        event_type: str,
        sentiment_score: float,
        headline: str,
    ) -> SignalDirection:
        if event_type == "monetary_policy":
            if "hawkish" in headline or "higher for longer" in headline:
                if symbol in {"XAUUSD", "XAGUSD"}:
                    return SignalDirection.SHORT
                if symbol in {"USD", "DXY"}:
                    return SignalDirection.LONG

            if (
                "dovish" in headline
                or "rate cut" in headline
                or "rate cuts" in headline
                or "cuts interest rates" in headline
            ):
                if symbol in {"XAUUSD", "XAGUSD"}:
                    return SignalDirection.LONG
                if symbol in {"USD", "DXY"}:
                    return SignalDirection.SHORT

            if (
                "rate hike" in headline
                or "rate hikes" in headline
                or "raises interest rates" in headline
            ):
                if symbol in {"XAUUSD", "XAGUSD"}:
                    return SignalDirection.SHORT
                if symbol in {"USD", "DXY"}:
                    return SignalDirection.LONG

        if event_type == "commodity" and symbol in {
            "XAUUSD",
            "XAGUSD",
            "USOIL",
            "UKOIL",
        }:
            if sentiment_score > 0:
                return SignalDirection.LONG
            if sentiment_score < 0:
                return SignalDirection.SHORT
            return SignalDirection.FLAT

        if sentiment_score > 0:
            return SignalDirection.LONG

        if sentiment_score < 0:
            return SignalDirection.SHORT

        return SignalDirection.FLAT

    @staticmethod
    def _calculate_confidence(
        *,
        event_type: str,
        sentiment_score: float,
        symbol: str,
    ) -> float:
        confidence = 0.50

        if event_type != "general_market":
            confidence += 0.15

        if abs(sentiment_score) >= 0.5:
            confidence += 0.15

        if symbol in {"XAUUSD", "XAGUSD", "USD", "DXY"}:
            confidence += 0.05

        return max(0.0, min(1.0, confidence))
