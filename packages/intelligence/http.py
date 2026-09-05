from __future__ import annotations

import asyncio
from collections.abc import Mapping
from types import TracebackType
from typing import Any, Self

import httpx


class IntelligenceHTTPError(RuntimeError):
    """Base exception for intelligence HTTP failures."""


class IntelligenceHTTPStatusError(IntelligenceHTTPError):
    """Raised when an intelligence API returns an unsuccessful HTTP status."""

    def __init__(
        self,
        *,
        status_code: int,
        url: str,
        message: str,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url


class IntelligenceHTTPTransport:
    """Resilient asynchronous HTTP transport for intelligence providers."""

    def __init__(
        self,
        *,
        base_url: str,
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        backoff_seconds: float = 0.5,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        normalized_base_url = base_url.strip().rstrip("/")

        if not normalized_base_url:
            raise ValueError("base_url must not be empty")

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

        if max_retries < 0:
            raise ValueError("max_retries must not be negative")

        if backoff_seconds < 0:
            raise ValueError("backoff_seconds must not be negative")

        self.base_url = normalized_base_url
        self.headers = dict(headers or {})
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def start(self) -> None:
        """Initialize the underlying HTTP client when required."""

        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=self.timeout_seconds,
            )

    async def close(self) -> None:
        """Close the underlying HTTP client when owned by this transport."""

        if self._client is not None and self._owns_client:
            await self._client.aclose()

        if self._owns_client:
            self._client = None

    async def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str | int | float | None] | None = None,
    ) -> Any:
        """GET JSON from a provider endpoint with bounded retries."""

        if self._client is None:
            await self.start()

        assert self._client is not None

        request_path = path.strip()
        if not request_path:
            raise ValueError("path must not be empty")

        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await self._client.get(
                    request_path,
                    params=params,
                )

                if response.is_success:
                    return response.json()

                if not self._is_retryable_status(response.status_code):
                    raise IntelligenceHTTPStatusError(
                        status_code=response.status_code,
                        url=str(response.url),
                        message=(
                            "Intelligence provider returned "
                            f"HTTP {response.status_code}"
                        ),
                    )

                last_error = IntelligenceHTTPStatusError(
                    status_code=response.status_code,
                    url=str(response.url),
                    message=(
                        "Intelligence provider returned "
                        f"retryable HTTP {response.status_code}"
                    ),
                )

            except IntelligenceHTTPStatusError as exc:
                last_error = exc
                if not self._is_retryable_status(exc.status_code):
                    raise

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc

            if attempt < self.max_retries:
                await asyncio.sleep(
                    self.backoff_seconds * (2**attempt)
                )

        if last_error is None:
            raise IntelligenceHTTPError(
                "Intelligence provider request failed without an error"
            )

        if isinstance(last_error, IntelligenceHTTPStatusError):
            raise last_error

        raise IntelligenceHTTPError(
            f"Intelligence provider request failed: {last_error}"
        ) from last_error

    @staticmethod
    def _is_retryable_status(status_code: int) -> bool:
        """Return whether an HTTP status is appropriate for retry."""

        return status_code == 408 or status_code == 429 or status_code >= 500