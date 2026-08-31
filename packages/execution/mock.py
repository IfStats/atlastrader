from decimal import Decimal

from packages.core.enums import OrderStatus, PositionStatus
from packages.core.models import Instrument, Order, Position
from packages.execution.interfaces import ExecutionProvider


class MockExecutionProvider(ExecutionProvider):
    """Deterministic execution provider for development and testing."""

    def __init__(
        self,
        *,
        balance: Decimal = Decimal(10000),
        instruments: dict[str, Instrument] | None = None,
    ) -> None:
        self._balance = balance
        self._instruments = instruments or {}
        self._connected = False
        self._orders: dict[str, Order] = {}
        self._positions: dict[str, Position] = {}

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def is_connected(self) -> bool:
        return self._connected

    async def get_account_balance(self) -> float:
        return float(self._balance)

    async def get_instrument(self, symbol: str) -> Instrument:
        if symbol not in self._instruments:
            raise KeyError(f"Instrument not found: {symbol}")

        return self._instruments[symbol]

    async def submit_order(self, order: Order) -> Order:
        if not self._connected:
            raise RuntimeError("Execution provider is not connected")

        if order.symbol not in self._instruments:
            raise KeyError(f"Instrument not found: {order.symbol}")

        filled_order = order.model_copy(
            update={
                "status": OrderStatus.FILLED,
            }
        )

        self._orders[order.id] = filled_order

        return filled_order

    async def cancel_order(self, order_id: str) -> Order:
        if order_id not in self._orders:
            raise KeyError(f"Order not found: {order_id}")

        order = self._orders[order_id]

        cancelled_order = order.model_copy(
            update={
                "status": OrderStatus.CANCELLED,
            }
        )

        self._orders[order_id] = cancelled_order

        return cancelled_order

    async def get_order(self, order_id: str) -> Order:
        if order_id not in self._orders:
            raise KeyError(f"Order not found: {order_id}")

        return self._orders[order_id]

    async def get_position(self, symbol: str) -> Position | None:
        return self._positions.get(symbol)

    async def get_positions(self) -> list[Position]:
        """Return all current open positions."""

        return [
            position
            for position in self._positions.values()
            if position.status is PositionStatus.OPEN
        ]

    async def close_position(self, symbol: str) -> Position:
        if symbol not in self._positions:
            raise KeyError(f"Position not found: {symbol}")

        position = self._positions[symbol]

        closed_position = position.model_copy(
            update={
                "status": PositionStatus.CLOSED,
            }
        )

        self._positions[symbol] = closed_position

        return closed_position

    def add_instrument(self, instrument: Instrument) -> None:
        """Register an instrument with the mock execution venue."""
        self._instruments[instrument.symbol] = instrument

    def add_position(self, position: Position) -> None:
        """Add a position to the mock execution venue."""
        self._positions[position.symbol] = position