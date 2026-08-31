from abc import ABC, abstractmethod

from packages.core.models import Instrument, Order, Position


class ExecutionProvider(ABC):
    """Interface between AtlasTrader and an execution venue."""

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
        """Return the current connection state."""
        raise NotImplementedError

    @abstractmethod
    async def get_account_balance(self) -> float:
        """Return the current account balance."""
        raise NotImplementedError

    @abstractmethod
    async def get_instrument(self, symbol: str) -> Instrument:
        """Return broker metadata for an instrument."""
        raise NotImplementedError

    @abstractmethod
    async def submit_order(self, order: Order) -> Order:
        """Submit an order to the execution venue."""
        raise NotImplementedError

    @abstractmethod
    async def get_position(self, symbol: str) -> Position | None:
        """Return the current position for an instrument."""
        raise NotImplementedError

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Return all current positions from the execution venue."""
        raise NotImplementedError