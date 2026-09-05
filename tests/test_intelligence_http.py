from unittest.mock import AsyncMock

import httpx
import pytest

from packages.intelligence.http import (
    IntelligenceHTTPError,
    IntelligenceHTTPStatusError,
    IntelligenceHTTPTransport,
)


def make_response(
    status_code: int,
    *,
    json_data: object | None = None,
) -> httpx.Response:
    request = httpx.Request(
        "GET",
        "https://provider.test/news",
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
        json_data={"items": [{"id": "1"}]},
    )

    transport = IntelligenceHTTPTransport(
        base_url="https://provider.test/",
        client=client,
    )

    result = await transport.get_json(
        "/news",
        params={"symbol": "XAUUSD"},
    )

    assert result == {"items": [{"id": "1"}]}

    client.get.assert_awaited_once_with(
        "/news",
        params={"symbol": "XAUUSD"},
    )


@pytest.mark.asyncio
async def test_transport_rejects_empty_path() -> None:
    client = AsyncMock(spec=httpx.AsyncClient)

    transport = IntelligenceHTTPTransport(
        base_url="https://provider.test",
        client=client,
    )

    with pytest.raises(ValueError, match="path must not be empty"):
        await transport.get_json("   ")


@pytest.mark.asyncio
async def test_transport_raises_non_retryable_status() -> None:
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = make_response(401)

    transport = IntelligenceHTTPTransport(
        base_url="https://provider.test",
        client=client,
        max_retries=3,
    )

    with pytest.raises(
        IntelligenceHTTPStatusError,
        match="HTTP 401",
    ) as exc_info:
        await transport.get_json("/news")

    assert exc_info.value.status_code == 401
    client.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_transport_retries_retryable_status() -> None:
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.side_effect = [
        make_response(503),
        make_response(503),
        make_response(
            200,
            json_data={"items": []},
        ),
    ]

    transport = IntelligenceHTTPTransport(
        base_url="https://provider.test",
        client=client,
        max_retries=2,
        backoff_seconds=0,
    )

    result = await transport.get_json("/news")

    assert result == {"items": []}
    assert client.get.await_count == 3


@pytest.mark.asyncio
async def test_transport_retries_network_errors() -> None:
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.side_effect = [
        httpx.ConnectError(
            "connection failed",
            request=httpx.Request(
                "GET",
                "https://provider.test/news",
            ),
        ),
        make_response(
            200,
            json_data={"items": []},
        ),
    ]

    transport = IntelligenceHTTPTransport(
        base_url="https://provider.test",
        client=client,
        max_retries=1,
        backoff_seconds=0,
    )

    result = await transport.get_json("/news")

    assert result == {"items": []}
    assert client.get.await_count == 2


@pytest.mark.asyncio
async def test_transport_exhausted_retries_raise_transport_error() -> None:
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.side_effect = httpx.ConnectError(
        "connection failed",
        request=httpx.Request(
            "GET",
            "https://provider.test/news",
        ),
    )

    transport = IntelligenceHTTPTransport(
        base_url="https://provider.test",
        client=client,
        max_retries=1,
        backoff_seconds=0,
    )

    with pytest.raises(
        IntelligenceHTTPError,
        match="request failed",
    ):
        await transport.get_json("/news")

    assert client.get.await_count == 2


@pytest.mark.asyncio
async def test_transport_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError, match="base_url"):
        IntelligenceHTTPTransport(base_url=" ")

    with pytest.raises(ValueError, match="timeout_seconds"):
        IntelligenceHTTPTransport(
            base_url="https://provider.test",
            timeout_seconds=0,
        )

    with pytest.raises(ValueError, match="max_retries"):
        IntelligenceHTTPTransport(
            base_url="https://provider.test",
            max_retries=-1,
        )

    with pytest.raises(ValueError, match="backoff_seconds"):
        IntelligenceHTTPTransport(
            base_url="https://provider.test",
            backoff_seconds=-1,
        )


@pytest.mark.asyncio
async def test_transport_context_manager_closes_owned_client() -> None:
    transport = IntelligenceHTTPTransport(
        base_url="https://provider.test",
    )

    await transport.start()

    assert transport._client is not None

    client = transport._client
    assert client is not None

    await transport.close()

    assert transport._client is None
    assert client.is_closed is True