from decimal import Decimal

from packages.core.models import MarketState, Order, Position
from packages.execution.interfaces import ExecutionProvider
from packages.execution.safety import (
    DefaultExecutionSafetyGate,
    ExecutionSafetyGate,
)
from packages.portfolio.models import PortfolioSnapshot
from packages.risk.interfaces import RiskManager


class ExecutionService:
    """Coordinates risk validation, execution safety, and order execution."""

    def __init__(
        self,
        *,
        provider: ExecutionProvider,
        risk_manager: RiskManager,
        portfolio: PortfolioSnapshot | None = None,
        safety_gate: ExecutionSafetyGate | None = None,
    ) -> None:
        self.provider = provider
        self.risk_manager = risk_manager
        self.portfolio = portfolio
        self.safety_gate = safety_gate or DefaultExecutionSafetyGate(
            provider=provider
        )

    async def submit_order(
        self,
        order: Order,
        *,
        market_state: MarketState | None = None,
    ) -> Order:
        """Validate, authorize, and submit an order."""

        portfolio = self.portfolio

        if portfolio is None:
            portfolio = PortfolioSnapshot(
                balance=Decimal(0),
                equity=Decimal(0),
                open_positions=0,
                total_exposure=Decimal(0),
            )

        approved = self.risk_manager.validate_order(
            order,
            portfolio,
            market_state,
        )

        if not approved:
            return order.model_copy(
                update={
                    "status": "rejected",
                }
            )

        safety_decision = await self.safety_gate.authorize(
            order,
            market_state=market_state,
        )

        if not safety_decision.authorized:
            return order.model_copy(
                update={
                    "status": "rejected",
                }
            )

        return await self.provider.submit_order(order)

    async def get_position(
        self,
        symbol: str,
    ) -> Position | None:
        """Return the current position for an instrument."""

        return await self.provider.get_position(symbol)