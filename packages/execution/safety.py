from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from packages.core.models import Instrument, MarketState, Order
from packages.execution.interfaces import ExecutionProvider


@dataclass(frozen=True, slots=True)
class ExecutionSafetyDecision:
    """Structured result of a pre-execution safety assessment."""

    authorized: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def allow(cls) -> ExecutionSafetyDecision:
        """Create an authorization decision."""
        return cls(authorized=True)

    @classmethod
    def block(cls, *reasons: str) -> ExecutionSafetyDecision:
        """Create a blocked decision with explicit reasons."""
        return cls(
            authorized=False,
            reasons=tuple(reasons),
        )


class ExecutionAuthorizationProvider(Protocol):
    """Optional venue authorization capabilities."""

    async def get_terminal_snapshot(self) -> object:
        """Return terminal authorization state."""
        ...

    async def get_account_snapshot(self) -> object:
        """Return account authorization state."""
        ...


class ExecutionSafetyGate:
    """Interface for mandatory pre-execution safety authorization."""

    async def authorize(
        self,
        order: Order,
        *,
        market_state: MarketState | None = None,
    ) -> ExecutionSafetyDecision:
        """Determine whether an order is safe to submit."""
        raise NotImplementedError


class DefaultExecutionSafetyGate(ExecutionSafetyGate):
    """Default venue-level execution safety gate."""

    def __init__(self, *, provider: ExecutionProvider) -> None:
        self.provider = provider

    async def authorize(
        self,
        order: Order,
        *,
        market_state: MarketState | None = None,
    ) -> ExecutionSafetyDecision:
        """Run mandatory pre-submission execution checks."""

        reasons: list[str] = []

        if not await self._is_connected():
            reasons.append("Execution provider is not connected")

        instrument: Instrument | None = None

        try:
            instrument = await self._get_instrument(order.symbol)
        except (KeyError, RuntimeError, ValueError) as exc:
            reasons.append(
                f"Instrument check failed for {order.symbol}: {exc}"
            )

        if instrument is not None:
            if not instrument.enabled:
                reasons.append(
                    f"Instrument is not enabled: {order.symbol}"
                )

            if order.quantity < instrument.min_volume:
                reasons.append(
                    f"Order quantity {order.quantity} is below "
                    f"minimum volume {instrument.min_volume}"
                )

            if (
                instrument.max_volume is not None
                and order.quantity > instrument.max_volume
            ):
                reasons.append(
                    f"Order quantity {order.quantity} exceeds "
                    f"maximum volume {instrument.max_volume}"
                )

            if order.quantity % instrument.volume_step != 0:
                reasons.append(
                    f"Order quantity {order.quantity} must be aligned "
                    f"with volume step {instrument.volume_step}"
                )

        if order.quantity <= Decimal(0):
            reasons.append("Order quantity must be greater than zero")

        if market_state is not None:
            if market_state.symbol != order.symbol:
                reasons.append(
                    "Market state symbol does not match order symbol"
                )

            if not market_state.is_tradeable:
                reasons.append(
                    f"Market is not tradeable: {order.symbol}"
                )

            if market_state.price <= Decimal(0):
                reasons.append(
                    f"Invalid market price: {order.symbol}"
                )

            if market_state.spread < Decimal(0):
                reasons.append(
                    f"Invalid market spread: {order.symbol}"
                )

        try:
            position = await self.provider.get_position(order.symbol)
        except (KeyError, RuntimeError, ValueError) as exc:
            reasons.append(
                f"Position check failed for {order.symbol}: {exc}"
            )
        else:
            if position is not None:
                reasons.append(
                    f"Existing position blocks new order: {order.symbol}"
                )

        authorization_reasons = await self._check_venue_authorization()
        reasons.extend(authorization_reasons)

        if reasons:
            return ExecutionSafetyDecision.block(*reasons)

        return ExecutionSafetyDecision.allow()

    async def _is_connected(self) -> bool:
        """Return whether the execution provider is connected."""
        return await self.provider.is_connected()

    async def _get_instrument(self, symbol: str) -> Instrument:
        """Retrieve instrument metadata from the execution provider."""
        return await self.provider.get_instrument(symbol)

    async def _check_venue_authorization(self) -> list[str]:
        """Check optional venue-specific authorization capabilities."""

        provider = self.provider
        reasons: list[str] = []

        get_terminal_snapshot = getattr(
            provider,
            "get_terminal_snapshot",
            None,
        )
        get_account_snapshot = getattr(
            provider,
            "get_account_snapshot",
            None,
        )

        if get_terminal_snapshot is None:
            return reasons

        terminal = await get_terminal_snapshot()

        if not bool(getattr(terminal, "connected", True)):
            reasons.append("Execution terminal is not connected")

        if bool(getattr(terminal, "tradeapi_disabled", False)):
            reasons.append("Execution trade API is disabled")

        if not bool(getattr(terminal, "trade_allowed", True)):
            reasons.append("Execution terminal trading is disabled")

        if get_account_snapshot is None:
            return reasons

        account = await get_account_snapshot()

        if not bool(getattr(account, "trade_allowed", True)):
            reasons.append("Execution account trading is not allowed")

        if not bool(getattr(account, "trade_expert", True)):
            reasons.append(
                "Execution account expert trading is not allowed"
            )

        return reasons