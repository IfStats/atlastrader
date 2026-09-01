from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status

from apps.api.dependencies import get_runtime
from apps.api.schemas import (
    ErrorResponse,
    HealthResponse,
    PortfolioResponse,
    PositionResponse,
    PositionsResponse,
    RuntimeStatusResponse,
)
from packages.core.config import MT5Settings, RiskSettings, RuntimeSettings
from packages.core.enums import Timeframe
from packages.core.models import Position
from packages.runtime.factory import create_runtime
from packages.runtime.service import TradingRuntime

RuntimeDependency = Annotated[TradingRuntime, Depends(get_runtime)]


def build_runtime() -> TradingRuntime:
    """Build the application's authoritative runtime."""

    runtime_settings = RuntimeSettings()
    risk_settings = RiskSettings()
    mt5_settings = MT5Settings()

    return create_runtime(
        symbols=runtime_settings.get_symbols(),
        settings=risk_settings,
        mt5_settings=mt5_settings,
        balance=runtime_settings.initial_balance,
        timeframe=Timeframe(runtime_settings.timeframe),
        candle_lookback=runtime_settings.candle_lookback,
        interval_seconds=runtime_settings.scan_interval_seconds,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create the runtime and clean it up when the application stops."""

    app.state.runtime = build_runtime()

    try:
        yield
    finally:
        runtime: TradingRuntime | None = getattr(
            app.state,
            "runtime",
            None,
        )

        if runtime is not None and runtime.started:
            await runtime.stop()


app = FastAPI(
    title="AtlasTrader API",
    version="1.0.0",
    description="Operational API boundary for AtlasTrader.",
    lifespan=lifespan,
)


def _position_response(position: Position) -> PositionResponse:
    """Convert a domain position into the public API contract."""

    return PositionResponse(
        symbol=position.symbol,
        side=position.side.value,
        status=position.status.value,
        quantity=position.quantity,
        entry_price=position.entry_price,
        current_price=position.current_price,
        stop_loss=position.stop_loss,
        take_profit=position.take_profit,
        opened_at=position.opened_at,
        closed_at=position.closed_at,
        realized_pnl=position.realized_pnl,
        unrealized_pnl=position.unrealized_pnl,
    )


def _runtime_status_response(
    runtime: TradingRuntime,
    execution_connected: bool,
) -> RuntimeStatusResponse:
    """Build the public runtime status response."""

    return RuntimeStatusResponse(
        status="running" if runtime.is_running else "stopped",
        started=runtime.started,
        running=runtime.is_running,
        execution_connected=execution_connected,
        symbols=list(runtime.symbols),
        interval_seconds=runtime.interval_seconds,
    )


def _portfolio_response(runtime: TradingRuntime) -> PortfolioResponse:
    """Build the public portfolio response."""

    snapshot = runtime.portfolio.snapshot()

    return PortfolioResponse(
        balance=snapshot.balance,
        equity=snapshot.equity,
        realized_pnl=snapshot.realized_pnl,
        unrealized_pnl=snapshot.unrealized_pnl,
        net_pnl=snapshot.net_pnl,
        open_positions=snapshot.open_positions,
        total_exposure=snapshot.total_exposure,
        available_equity=snapshot.available_equity,
        open_symbols=list(snapshot.open_symbols),
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="API liveness",
)
async def health() -> HealthResponse:
    """Return API process liveness."""

    return HealthResponse(status="ok")


@app.get(
    "/status",
    response_model=RuntimeStatusResponse,
    summary="Runtime status",
)
async def runtime_status(
    runtime: RuntimeDependency,
) -> RuntimeStatusResponse:
    """Return the current runtime and execution connection state."""

    execution_connected = await runtime.execution_provider.is_connected()

    return _runtime_status_response(
        runtime,
        execution_connected,
    )


@app.post(
    "/runtime/start",
    response_model=RuntimeStatusResponse,
    summary="Start trading runtime",
)
async def start_runtime(
    runtime: RuntimeDependency,
) -> RuntimeStatusResponse:
    """Start the trading runtime."""

    await runtime.start()

    execution_connected = await runtime.execution_provider.is_connected()

    return _runtime_status_response(
        runtime,
        execution_connected,
    )


@app.post(
    "/runtime/stop",
    response_model=RuntimeStatusResponse,
    summary="Stop trading runtime",
)
async def stop_runtime(
    runtime: RuntimeDependency,
) -> RuntimeStatusResponse:
    """Stop the trading runtime."""

    await runtime.stop()

    execution_connected = await runtime.execution_provider.is_connected()

    return _runtime_status_response(
        runtime,
        execution_connected,
    )


@app.post(
    "/runtime/reconcile",
    response_model=PortfolioResponse,
    summary="Reconcile trading portfolio",
)
async def reconcile_runtime(
    runtime: RuntimeDependency,
) -> PortfolioResponse:
    """Reconcile broker account state with the local portfolio."""

    await runtime.reconcile()

    return _portfolio_response(runtime)


@app.get(
    "/portfolio",
    response_model=PortfolioResponse,
    summary="Portfolio snapshot",
)
async def portfolio(
    runtime: RuntimeDependency,
) -> PortfolioResponse:
    """Return the current portfolio snapshot."""

    return _portfolio_response(runtime)


@app.get(
    "/positions",
    response_model=PositionsResponse,
    summary="Tracked positions",
)
async def positions(
    runtime: RuntimeDependency,
) -> PositionsResponse:
    """Return all positions currently tracked locally."""

    return PositionsResponse(
        positions=[
            _position_response(position)
            for position in runtime.portfolio.positions()
        ]
    )


@app.get(
    "/positions/{symbol}",
    response_model=PositionResponse,
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Position not found",
        }
    },
    summary="Get position",
)
async def position(
    symbol: str,
    runtime: RuntimeDependency,
) -> PositionResponse:
    """Return one tracked position."""

    normalized_symbol = symbol.strip().upper()

    tracked_position = runtime.portfolio.get_position(normalized_symbol)

    if tracked_position is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "POSITION_NOT_FOUND",
                "message": (
                    f"No tracked position exists for {normalized_symbol}."
                ),
            },
        )

    return _position_response(tracked_position)