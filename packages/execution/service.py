from datetime import UTC, datetime

from packages.core.models import MarketState, Order, Position
from packages.execution.interfaces import ExecutionProvider
from packages.risk.interfaces import RiskManager


class ExecutionService:
    """Coordinates risk validation and order execution."""

    def __init__(
        self,
        provider: ExecutionProvider,
        risk_manager: RiskManager,
    ) -> None:
        self.provider = provider
        self.risk_manager = risk_manager

    async def connect(self) -> None:
        """Connect to the execution venue."""
        await self.provider.connect()

    async def disconnect(self) -> None:
        """Disconnect from the execution venue."""
        await self.provider.disconnect()

    async def execute_order(
        self,
        order: Order,
        market_state: MarketState | None = None,
        open_positions: int = 0,
    ) -> Order:
        """Validate and execute an order."""

        if not self.risk_manager.validate_order(
            order,
            market_state,
            open_positions,
        ):
            return order.model_copy(
                update={
                    "status": "rejected",
                    "updated_at": datetime.now(UTC),
                }
            )

        return await self.provider.submit_order(order)

    async def get_position(
        self,
        symbol: str,
    ) -> Position | None:
        """Return the current position for an instrument."""
        return await self.provider.get_position(symbol)