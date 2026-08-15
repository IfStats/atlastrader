from abc import ABC, abstractmethod

from packages.core.models import Instrument, Order, Position


class ExecutionProvider(ABC):
    """Abstract interface for a trading execution venue."""

    @abstractmethod
    async def connect(self) -> None:
        """Connect to the execution venue."""
        raise NotImplementedError

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the execution venue."""
        raise NotImplementedError

    @abstractmethod
    async def is_connected(self) -> bool:
        """Return whether the execution venue is connected."""
        raise NotImplementedError

    @abstractmethod
    async def get_account_balance(self) -> float:
        """Return the current account balance."""
        raise NotImplementedError

    @abstractmethod
    async def get_instrument(self, symbol: str) -> Instrument:
        """Return instrument metadata for a symbol."""
        raise NotImplementedError

    @abstractmethod
    async def submit_order(self, order: Order) -> Order:
        """Submit an order to the execution venue."""
        raise NotImplementedError

    @abstractmethod
    async def cancel_order(self, order_id: str) -> Order:
        """Cancel an existing order."""
        raise NotImplementedError

    @abstractmethod
    async def get_order(self, order_id: str) -> Order:
        """Return an existing order by ID."""
        raise NotImplementedError

    @abstractmethod
    async def get_position(self, symbol: str) -> Position | None:
        """Return the current position for a symbol, if one exists."""
        raise NotImplementedError

    @abstractmethod
    async def close_position(self, symbol: str) -> Position:
        """Close the current position for a symbol."""
        raise NotImplementedError