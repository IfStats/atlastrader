from __future__ import annotations

from abc import abstractmethod
from datetime import datetime
from typing import Any

from packages.core.intelligence import MarketEvent, MarketNews
from packages.intelligence.http import IntelligenceHTTPTransport
from packages.intelligence.interfaces import MarketIntelligenceProvider


class HTTPMarketIntelligenceProvider(MarketIntelligenceProvider):
    """Base provider for market intelligence APIs accessed over HTTP."""

    def __init__(
        self,
        *,
        base_url: str,
        headers: dict[str, str] | None = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        backoff_seconds: float = 0.5,
    ) -> None:
        self.transport = IntelligenceHTTPTransport(
            base_url=base_url,
            headers=headers,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
        )

    async def start(self) -> None:
        """Start the provider's HTTP transport."""

        await self.transport.start()

    async def close(self) -> None:
        """Close the provider's HTTP transport."""

        await self.transport.close()

    async def get_news(
        self,
        *,
        start: datetime,
        end: datetime,
        symbols: list[str] | None = None,
    ) -> list[MarketNews]:
        """Fetch and parse provider news."""

        try:
            payload = await self.fetch_news(
                start=start,
                end=end,
                symbols=symbols,
            )
            return self.parse_news(payload)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"{self.name} news request failed: {type(exc).__name__}: {exc}"
            ) from exc

    async def get_events(
        self,
        *,
        start: datetime,
        end: datetime,
        symbols: list[str] | None = None,
    ) -> list[MarketEvent]:
        """Fetch and parse provider events."""

        try:
            payload = await self.fetch_events(
                start=start,
                end=end,
                symbols=symbols,
            )
            return self.parse_events(payload)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"{self.name} events request failed: {type(exc).__name__}: {exc}"
            ) from exc

    @abstractmethod
    async def fetch_news(
        self,
        *,
        start: datetime,
        end: datetime,
        symbols: list[str] | None,
    ) -> Any:
        """Fetch the provider's raw news payload."""

    @abstractmethod
    async def fetch_events(
        self,
        *,
        start: datetime,
        end: datetime,
        symbols: list[str] | None,
    ) -> Any:
        """Fetch the provider's raw event payload."""

    @abstractmethod
    def parse_news(self, payload: Any) -> list[MarketNews]:
        """Convert a raw news payload into canonical market news."""

    @abstractmethod
    def parse_events(self, payload: Any) -> list[MarketEvent]:
        """Convert a raw event payload into canonical market events."""