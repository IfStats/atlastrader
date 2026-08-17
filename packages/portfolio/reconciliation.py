from decimal import Decimal

from packages.core.models import Position
from packages.execution.interfaces import ExecutionProvider
from packages.portfolio.models import PortfolioSnapshot
from packages.portfolio.service import PortfolioService


class PortfolioReconciliationService:
    """Synchronizes local portfolio state with an execution venue."""

    def __init__(
        self,
        *,
        provider: ExecutionProvider,
        portfolio: PortfolioService,
    ) -> None:
        self.provider = provider
        self.portfolio = portfolio

    def set_balance(self, balance: Decimal) -> None:
        """Update the portfolio account balance."""

        if balance < Decimal(0):
            raise ValueError(
                "balance must be greater than or equal to zero"
            )

        self._balance = balance

    async def reconcile(
        self,
        symbols: list[str],
    ) -> PortfolioSnapshot:
        """Reconcile tracked positions and account balance."""

        balance = Decimal(
            str(await self.provider.get_account_balance())
        )

        self.portfolio.set_balance(balance)

        broker_positions: dict[str, Position] = {}

        for symbol in symbols:
            position = await self.provider.get_position(symbol)

            if position is not None:
                broker_positions[symbol] = position

        local_positions = {
            position.symbol: position
            for position in self.portfolio.positions()
        }

        for symbol, broker_position in broker_positions.items():
            local_position = local_positions.get(symbol)

            if local_position is None:
                self.portfolio.add_position(broker_position)
                continue

            self.portfolio.add_position(
                local_position.model_copy(
                    update={
                        "side": broker_position.side,
                        "status": broker_position.status,
                        "quantity": broker_position.quantity,
                        "entry_price": broker_position.entry_price,
                        "current_price": broker_position.current_price,
                        "stop_loss": broker_position.stop_loss,
                        "take_profit": broker_position.take_profit,
                        "opened_at": broker_position.opened_at,
                        "realized_pnl": broker_position.realized_pnl,
                        "unrealized_pnl": broker_position.unrealized_pnl,
                    }
                )
            )

        for symbol in local_positions:
            if symbol not in broker_positions:
                self.portfolio.remove_position(symbol)

        return self.portfolio.snapshot()