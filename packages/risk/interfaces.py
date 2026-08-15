from abc import ABC, abstractmethod
from decimal import Decimal

from packages.core.models import MarketState, Order, Signal


class RiskManager(ABC):
    """Interface for AtlasTrader risk management."""

    @abstractmethod
    def can_trade(
        self,
        daily_loss: Decimal,
        open_positions: int = 0,
    ) -> bool:
        """Return whether trading is currently permitted."""
        raise NotImplementedError

    @abstractmethod
    def approve_signal(
        self,
        signal: Signal,
        market_state: MarketState,
        open_positions: int = 0,
    ) -> bool:
        """Determine whether a signal passes risk controls."""
        raise NotImplementedError

    @abstractmethod
    def validate_order(
        self,
        order: Order,
        market_state: MarketState | None = None,
        open_positions: int = 0,
    ) -> bool:
        """Determine whether an order passes risk controls."""
        raise NotImplementedError

    @abstractmethod
    def calculate_position_size(
        self,
        account_balance: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
        contract_size: Decimal,
        risk_fraction: Decimal | None = None,
    ) -> Decimal:
        """Calculate a risk-based position size."""
        raise NotImplementedError