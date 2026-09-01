from typing import cast

from fastapi import Request

from packages.runtime.service import TradingRuntime


def get_runtime(request: Request) -> TradingRuntime:
    """Return the application's authoritative trading runtime."""

    return cast(
        TradingRuntime,
        request.app.state.runtime,
    )