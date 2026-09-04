from abc import ABC, abstractmethod
from datetime import datetime

from packages.core.intelligence import MarketEvent, MarketNews


class MarketIntelligenceProvider(ABC):
    @property
    def name(self) -> str:
        """Stable adapter name used for provenance and diagnostics."""
        return self.__class__.__name__

    @abstractmethod
    async def get_news(
        self,
        *,
        start: datetime,
        end: datetime,
        symbols: list[str] | None = None,
    ) -> list[MarketNews]:
        ...

    @abstractmethod
    async def get_events(
        self,
        *,
        start: datetime,
        end: datetime,
        symbols: list[str] | None = None,
    ) -> list[MarketEvent]:
        ...