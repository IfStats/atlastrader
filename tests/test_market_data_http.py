from unittest.mock import AsyncMock

import httpx
import pytest

from packages.market_data.http import (
    MarketDataHTTPError,
    MarketDataHTTPStatusError,
    MarketDataHTTPTransport,
)


def make_response(
    status_code: int,
    *,
    json_data: object | None = None,
) -> httpx.Response:
    request = httpx.Request(
        "GET",
        "https://provider.test/market-data",
    )

    return httpx.Response(
        status_code,
        request=request,
        json=json_data,
    )


@pytest.mark.asyncio
async def test_transport_get_json_returns_json() -> None:
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = make_response(
        200,
        json_data={"results": [{"symbol": "XAUUSD"}]},
    )

    transport = MarketDataHTTPTransport(
        base_url="https://provider.test/",
        client=client,
    )

    result = await transport.get_json(
        "/quote",
        params={"symbol": "XAUUSD"},
    )

    assert result == {"results": [{"symbol": "XAUUSD"}]}
    client.get.assert_awaited_once_with(
        "/quote",
        params={"symbol": "XAUUSD"},
    )


@pytest.mark.asyncio
async def test_transport_rejects_empty_path() -> None:
    client = AsyncMock(spec=httpx.AsyncClient)

    transport = MarketDataHTTPTransport(
        base_url="https://provider.test",
        client=client,
    )

    with pytest.raises(ValueError, match="path must not be empty"):
        await transport.get_json("   ")


@pytest.mark.asyncio
async def test_transport_raises_non_retryable_status() -> None:
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = make_response(401)

    transport = MarketDataHTTPTransport(
        base_url="https://provider.test",
        client=client,
        max_retries=3,
    )

    with pytest.raises(
        MarketDataHTTPStatusError,
        match="HTTP 401",
    ) as exc_info:
        await transport.get_json("/quote")

    assert exc_info.value.status_code == 401
    assert exc_info.value.url == "https://provider.test/market-data"
    client.get.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [408, 429, 500, 503])
async def test_transport_retries_retryable_status(status_code: int) -> None:
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.side_effect = [
        make_response(status_code),
        make_response(200, json_data={"results": []}),
    ]

    transport = MarketDataHTTPTransport(
        base_url="https://provider.test",
        client=client,
        max_retries=1,
        backoff_seconds=0,
    )

    result = await transport.get_json("/quote")

    assert result == {"results": []}
    assert client.get.await_count == 2


@pytest.mark.asyncio
async def test_transport_retries_network_errors() -> None:
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.side_effect = [
        httpx.ConnectError(
            "connection failed",
            request=httpx.Request(
                "GET",
                "https://provider.test/quote",
            ),
        ),
        make_response(200, json_data={"results": []}),
    ]

    transport = MarketDataHTTPTransport(
        base_url="https://provider.test",
        client=client,
        max_retries=1,
        backoff_seconds=0,
    )

    result = await transport.get_json("/quote")

    assert result == {"results": []}
    assert client.get.await_count == 2


@pytest.mark.asyncio
async def test_transport_retries_timeout_errors() -> None:
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.side_effect = [
        httpx.ReadTimeout(
            "timed out",
            request=httpx.Request(
                "GET",
                "https://provider.test/quote",
            ),
        ),
        make_response(200, json_data={"results": []}),
    ]

    transport = MarketDataHTTPTransport(
        base_url="https://provider.test",
        client=client,
        max_retries=1,
        backoff_seconds=0,
    )

    result = await transport.get_json("/quote")

    assert result == {"results": []}
    assert client.get.await_count == 2


@pytest.mark.asyncio
async def test_transport_exhausted_network_retries_raise_transport_error() -> None:
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.side_effect = httpx.ConnectError(
        "connection failed",
        request=httpx.Request(
            "GET",
            "https://provider.test/quote",
        ),
    )

    transport = MarketDataHTTPTransport(
        base_url="https://provider.test",
        client=client,
        max_retries=1,
        backoff_seconds=0,
    )

    with pytest.raises(
        MarketDataHTTPError,
        match="request failed",
    ):
        await transport.get_json("/quote")

    assert client.get.await_count == 2


@pytest.mark.asyncio
async def test_transport_exhausted_status_retries_preserve_status_error() -> None:
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = make_response(503)

    transport = MarketDataHTTPTransport(
        base_url="https://provider.test",
        client=client,
        max_retries=1,
        backoff_seconds=0,
    )

    with pytest.raises(MarketDataHTTPStatusError) as exc_info:
        await transport.get_json("/quote")

    assert exc_info.value.status_code == 503
    assert client.get.await_count == 2


@pytest.mark.asyncio
async def test_transport_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError, match="base_url"):
        MarketDataHTTPTransport(base_url=" ")

    with pytest.raises(ValueError, match="timeout_seconds"):
        MarketDataHTTPTransport(
            base_url="https://provider.test",
            timeout_seconds=0,
        )

    with pytest.raises(ValueError, match="max_retries"):
        MarketDataHTTPTransport(
            base_url="https://provider.test",
            max_retries=-1,
        )

    with pytest.raises(ValueError, match="backoff_seconds"):
        MarketDataHTTPTransport(
            base_url="https://provider.test",
            backoff_seconds=-1,
        )


@pytest.mark.asyncio
async def test_transport_close_closes_owned_client() -> None:
    transport = MarketDataHTTPTransport(
        base_url="https://provider.test",
    )

    await transport.start()

    assert transport._client is not None
    client = transport._client

    await transport.close()

    assert transport._client is None
    assert client.is_closed is True


@pytest.mark.asyncio
async def test_transport_close_does_not_close_injected_client() -> None:
    client = AsyncMock(spec=httpx.AsyncClient)

    transport = MarketDataHTTPTransport(
        base_url="https://provider.test",
        client=client,
    )

    await transport.close()

    client.aclose.assert_not_awaited()