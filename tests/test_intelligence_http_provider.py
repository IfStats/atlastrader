from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from packages.core.intelligence import MarketEvent, MarketNews
from packages.intelligence.http_provider import (
    HTTPMarketIntelligenceProvider,
)


class TestHTTPProvider(HTTPMarketIntelligenceProvider):
    @property
    def name(self) -> str:
        return "TestProvider"

    async def fetch_news(
        self,
        *,
        start: datetime,
        end: datetime,
        symbols: list[str] | None,
    ) -> object:
        return {"news": []}

    async def fetch_events(
        self,
        *,
        start: datetime,
        end: datetime,
        symbols: list[str] | None,
    ) -> object:
        return {"events": []}

    def parse_news(self, payload: object) -> list[MarketNews]:
        return []

    def parse_events(self, payload: object) -> list[MarketEvent]:
        return []


def make_provider() -> TestHTTPProvider:
    return TestHTTPProvider(
        base_url="https://provider.test",
    )


@pytest.mark.asyncio
async def test_provider_exposes_stable_name() -> None:
    provider = make_provider()

    assert provider.name == "TestProvider"


@pytest.mark.asyncio
async def test_provider_starts_and_closes_transport() -> None:
    provider = make_provider()

    await provider.start()

    assert provider.transport._client is not None

    await provider.close()

    assert provider.transport._client is None


@pytest.mark.asyncio
async def test_provider_delegates_news_fetch_and_parse() -> None:
    provider = make_provider()

    provider.fetch_news = AsyncMock(
        return_value={"news": [{"id": "1"}]},
    )

    provider.parse_news = lambda payload: [
        MarketNews(
            id="1",
            headline="Test",
            source="TestProvider",
            published_at=datetime.now(UTC),
        )
    ]

    result = await provider.get_news(
        start=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
        end=datetime(2026, 9, 5, 11, 0, tzinfo=UTC),
        symbols=["XAUUSD"],
    )

    assert len(result) == 1
    assert result[0].id == "1"
    provider.fetch_news.assert_awaited_once()


@pytest.mark.asyncio
async def test_provider_delegates_event_fetch_and_parse() -> None:
    provider = make_provider()

    provider.fetch_events = AsyncMock(
        return_value={"events": [{"id": "1"}]},
    )

    provider.parse_events = lambda payload: [
        MarketEvent(
            id="1",
            name="Test Event",
            event_type="economic_growth",
            scheduled_at=datetime.now(UTC),
            source="TestProvider",
        )
    ]

    result = await provider.get_events(
        start=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
        end=datetime(2026, 9, 5, 11, 0, tzinfo=UTC),
        symbols=["XAUUSD"],
    )

    assert len(result) == 1
    assert result[0].id == "1"
    provider.fetch_events.assert_awaited_once()


@pytest.mark.asyncio
async def test_provider_converts_parser_failure_to_runtime_error() -> None:
    provider = make_provider()

    provider.parse_news = lambda payload: (_ for _ in ()).throw(
        ValueError("invalid provider payload")
    )

    with pytest.raises(
        RuntimeError,
        match="TestProvider news request failed",
    ):
        await provider.get_news(
            start=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
            end=datetime(2026, 9, 5, 11, 0, tzinfo=UTC),
        )


@pytest.mark.asyncio
async def test_provider_preserves_runtime_errors() -> None:
    provider = make_provider()

    provider.fetch_news = AsyncMock(
        side_effect=RuntimeError("upstream unavailable"),
    )

    with pytest.raises(
        RuntimeError,
        match="upstream unavailable",
    ):
        await provider.get_news(
            start=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
            end=datetime(2026, 9, 5, 11, 0, tzinfo=UTC),
        )


@pytest.mark.asyncio
async def test_provider_passes_query_window_and_symbols() -> None:
    provider = make_provider()

    provider.fetch_news = AsyncMock(
        return_value={"news": []},
    )

    start = datetime(2026, 9, 5, 10, 0, tzinfo=UTC)
    end = datetime(2026, 9, 5, 11, 0, tzinfo=UTC)

    await provider.get_news(
        start=start,
        end=end,
        symbols=["XAUUSD", "EURUSD"],
    )

    provider.fetch_news.assert_awaited_once_with(
        start=start,
        end=end,
        symbols=["XAUUSD", "EURUSD"],
    )