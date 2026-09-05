from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from packages.core.intelligence import MarketNews
from packages.intelligence.http_provider import HTTPMarketIntelligenceProvider


class FinnhubMarketIntelligenceProvider(HTTPMarketIntelligenceProvider):
    """Finnhub market-news intelligence provider."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://finnhub.io/api/v1",
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        backoff_seconds: float = 0.5,
        category: str = "general",
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key must not be empty")

        if not category.strip():
            raise ValueError("category must not be empty")

        self.category = category.strip().lower()

        super().__init__(
            base_url=base_url,
            headers={"X-Finnhub-Token": api_key},
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
        )

    @property
    def name(self) -> str:
        """Return the stable provider identifier."""

        return "finnhub"

    async def fetch_news(
        self,
        *,
        start: datetime,
        end: datetime,
        symbols: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch Finnhub news for the requested time window."""

        del symbols

        payload = await self.transport.get_json(
            "/news",
            params={"category": self.category},
        )

        if not isinstance(payload, list):
            raise TypeError("Finnhub news response must be a list")

        return [
            item
            for item in payload
            if isinstance(item, dict)
            and self._is_timestamp_in_range(
                item.get("datetime"),
                start=start,
                end=end,
            )
        ]

    async def fetch_events(
        self,
        *,
        start: datetime,
        end: datetime,
        symbols: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Finnhub calendar events are not supplied by this adapter."""

        del start, end, symbols
        return []

    def parse_news(
        self,
        payload: list[dict[str, Any]],
    ) -> list[MarketNews]:
        """Convert Finnhub news records into MarketNews objects."""

        results: list[MarketNews] = []

        for item in payload:
            try:
                results.append(self._parse_news_item(item))
            except (KeyError, TypeError, ValueError):
                continue

        return results

    def parse_events(self, payload: Any) -> list[Any]:
        """Return no events because this adapter supplies news only."""

        del payload
        return []

    @staticmethod
    def _is_timestamp_in_range(
        value: object,
        *,
        start: datetime,
        end: datetime,
    ) -> bool:
        if not isinstance(value, (int, float)):
            return False

        published_at = datetime.fromtimestamp(value, tz=UTC)
        return start <= published_at <= end

    @staticmethod
    def _parse_news_item(
        item: dict[str, Any],
    ) -> MarketNews:
        article_id = item["id"]
        headline = item["headline"]
        timestamp = item["datetime"]

        if not isinstance(article_id, (int, str)):
            raise TypeError("Finnhub article id must be an integer or string")

        if not isinstance(headline, str) or not headline.strip():
            raise ValueError("Finnhub headline must not be empty")

        if not isinstance(timestamp, (int, float)):
            raise TypeError("Finnhub datetime must be a Unix timestamp")

        published_at = datetime.fromtimestamp(timestamp, tz=UTC)

        related = item.get("related", "")
        symbols = FinnhubMarketIntelligenceProvider._parse_symbols(related)

        source = item.get("source")
        if not isinstance(source, str) or not source.strip():
            source = "Finnhub"

        summary = item.get("summary")
        if not isinstance(summary, str):
            summary = None

        url = item.get("url")
        if not isinstance(url, str) or not url.strip():
            url = None

        category = item.get("category")
        if not isinstance(category, str) or not category.strip():
            category = None

        return MarketNews(
            id=f"finnhub-{article_id}",
            headline=headline.strip(),
            source=source.strip(),
            published_at=published_at,
            url=url,
            summary=summary,
            provider="finnhub",
            external_id=str(article_id),
            symbols=symbols,
            event_type=category,
        )

    @staticmethod
    def _parse_symbols(value: object) -> list[str]:
        if not isinstance(value, str):
            return []

        symbols = [
            symbol.strip().upper()
            for symbol in value.split(",")
            if symbol.strip()
        ]

        return list(dict.fromkeys(symbols))