from decimal import Decimal

from packages.core.models import Order, Position
from packages.execution.interfaces import ExecutionProvider
from packages.portfolio.service import PortfolioService


class PositionManager:
    """Coordinates broker positions and internal portfolio state."""

    def __init__(
        self,
        *,
        execution_provider: ExecutionProvider,
        portfolio: PortfolioService,
    ) -> None:
        self.execution_provider = execution_provider
        self.portfolio = portfolio

    def record_filled_order(self, order: Order) -> Position:
        """Create and record a portfolio position from a filled order."""

        if order.price is None:
            raise ValueError(
                "Filled order must have a price to create a position"
            )

        position = Position(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            entry_price=order.price,
            current_price=order.price,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            opened_at=order.updated_at,
        )

        self.portfolio.add_position(position)

        return position

    async def sync(self) -> list[Position]:
        """Synchronize internal positions with broker positions."""

        positions = await self.execution_provider.get_positions()

        broker_symbols = {position.symbol for position in positions}

        for position in positions:
            self.portfolio.add_position(position)

        for existing in self.portfolio.positions():
            if existing.symbol not in broker_symbols:
                self.portfolio.remove_position(existing.symbol)

        return self.portfolio.positions()

    async def sync_balance(self) -> Decimal:
        """Synchronize the portfolio balance with the broker."""

        balance = await self.execution_provider.get_account_balance()

        decimal_balance = Decimal(str(balance))

        self.portfolio.set_balance(decimal_balance)

        return decimal_balance

    async def sync_all(self) -> list[Position]:
        """Synchronize broker balance and positions."""

        await self.sync_balance()

        return await self.sync()