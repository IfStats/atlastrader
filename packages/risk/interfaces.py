from abc import ABC, abstractmethod
from decimal import Decimal

from packages.core.config import RiskSettings
from packages.core.models import MarketState, Order, Position, Signal


class RiskManager(ABC):
    """Interface for AtlasTrader's risk management engine."""

    @abstractmethod
    def approve_signal(
        self,
        signal: Signal,
        market_state: MarketState,
        open_positions: list[Position],
    ) -> bool:
        """Determine whether a trading signal passes risk controls."""
        raise NotImplementedError

    @abstractmethod
    def validate_order(
        self,
        order: Order,
        market_state: MarketState,
        open_positions: list[Position],
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
        """Calculate position size from account risk and stop distance."""
        raise NotImplementedError

    @abstractmethod
    def can_trade(self, daily_pnl: Decimal) -> bool:
        """Return whether trading is currently allowed."""
        raise NotImplementedError

    @property
    @abstractmethod
    def settings(self) -> RiskSettings:
        """Return the active risk configuration."""
        raise NotImplementedError