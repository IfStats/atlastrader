from datetime import UTC, datetime
from decimal import Decimal

from packages.core.enums import PositionStatus
from packages.core.models import Position
from packages.portfolio.models import PortfolioSnapshot


class PortfolioService:
    """Maintains the portfolio's current position state."""

    def __init__(
        self,
        *,
        balance: Decimal,
    ) -> None:
        if balance < Decimal(0):
            raise ValueError(
                "balance must be greater than or equal to zero"
            )

        self._balance = balance
        self._positions: dict[str, Position] = {}
        self._realized_pnl = Decimal(0)

    def set_balance(self, balance: Decimal) -> None:
        """Update the portfolio account balance."""

        if balance < Decimal(0):
            raise ValueError(
                "balance must be greater than or equal to zero"
            )

        self._balance = balance

    def add_position(self, position: Position) -> None:
        """Add or replace a tracked position."""

        self._positions[position.symbol] = position

    def remove_position(self, symbol: str) -> None:
        """Remove a tracked position."""

        self._positions.pop(symbol, None)

    def get_position(self, symbol: str) -> Position | None:
        """Return a tracked position."""

        return self._positions.get(symbol)

    def positions(self) -> list[Position]:
        """Return all tracked positions."""

        return list(self._positions.values())

    def update_position(
        self,
        symbol: str,
        *,
        current_price: Decimal,
        unrealized_pnl: Decimal,
    ) -> Position:
        """Update the current price and unrealized P&L of a position."""

        position = self._positions.get(symbol)

        if position is None:
            raise KeyError(f"Position not found: {symbol}")

        if position.status is not PositionStatus.OPEN:
            raise ValueError(f"Position is not open: {symbol}")

        updated_position = position.model_copy(
            update={
                "current_price": current_price,
                "unrealized_pnl": unrealized_pnl,
            }
        )

        self._positions[symbol] = updated_position

        return updated_position

    def mark_position(
        self,
        symbol: str,
        *,
        current_price: Decimal,
        contract_size: Decimal,
    ) -> Position:
        """Mark an open position to market and calculate unrealized P&L."""

        position = self._positions.get(symbol)

        if position is None:
            raise KeyError(f"Position not found: {symbol}")

        if position.status is not PositionStatus.OPEN:
            raise ValueError(f"Position is not open: {symbol}")

        if current_price <= Decimal(0):
            raise ValueError(
                "current_price must be greater than zero"
            )

        if contract_size <= Decimal(0):
            raise ValueError(
                "contract_size must be greater than zero"
            )

        price_change = current_price - position.entry_price

        if position.side.value == "sell":
            price_change = -price_change

        unrealized_pnl = (
            price_change
            * position.quantity
            * contract_size
        )

        return self.update_position(
            symbol,
            current_price=current_price,
            unrealized_pnl=unrealized_pnl,
        )

    def close_position(
        self,
        symbol: str,
        *,
        current_price: Decimal,
        realized_pnl: Decimal,
    ) -> Position:
        """Close an open position and record its realized P&L."""

        position = self._positions.get(symbol)

        if position is None:
            raise KeyError(f"Position not found: {symbol}")

        if position.status is not PositionStatus.OPEN:
            raise ValueError(f"Position is not open: {symbol}")

        closed_position = position.model_copy(
            update={
                "status": PositionStatus.CLOSED,
                "current_price": current_price,
                "realized_pnl": realized_pnl,
                "unrealized_pnl": Decimal(0),
                "closed_at": datetime.now(UTC),
            }
        )

        self._realized_pnl += realized_pnl
        self._positions.pop(symbol)

        return closed_position

    def snapshot(self) -> PortfolioSnapshot:
        """Build the current portfolio snapshot."""

        positions = self.positions()

        realized_pnl = self._realized_pnl + sum(
            (position.realized_pnl for position in positions),
            Decimal(0),
        )

        unrealized_pnl = sum(
            (position.unrealized_pnl for position in positions),
            Decimal(0),
        )

        total_exposure = sum(
            (
                position.entry_price * position.quantity
                for position in positions
            ),
            Decimal(0),
        )

        equity = self._balance + realized_pnl + unrealized_pnl

        return PortfolioSnapshot(
            balance=self._balance,
            equity=equity,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            open_positions=len(positions),
            total_exposure=total_exposure,
        )