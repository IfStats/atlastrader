from decimal import Decimal

from packages.core.config import RiskSettings
from packages.core.models import MarketState, Order, Signal
from packages.risk.interfaces import RiskManager


class DefaultRiskManager(RiskManager):
    """Default pre-trade risk-control implementation."""

    _DEFAULT_ACCOUNT_BALANCE = Decimal(10000)

    def __init__(self, settings: RiskSettings) -> None:
        self.settings = settings

    def can_trade(
        self,
        daily_loss: Decimal,
        open_positions: int = 0,
    ) -> bool:
        """Return whether current portfolio risk permits trading."""

        if not self.settings.trading_enabled:
            return False

        if open_positions >= self.settings.max_open_positions:
            return False

        max_daily_loss_amount = (
            self._DEFAULT_ACCOUNT_BALANCE * self.settings.max_daily_loss
        )

        return abs(daily_loss) < max_daily_loss_amount

    def approve_signal(
        self,
        signal: Signal,
        market_state: MarketState,
        open_positions: int = 0,
    ) -> bool:
        """Approve a strategy signal against risk controls."""

        if not self.settings.trading_enabled:
            return False

        if not market_state.is_tradeable:
            return False

        if open_positions >= self.settings.max_open_positions:
            return False

        return not market_state.spread > self.settings.max_spread

    def validate_order(
        self,
        order: Order,
        market_state: MarketState | None = None,
        open_positions: int = 0,
    ) -> bool:
        """Validate an order against risk constraints."""

        if not self.settings.trading_enabled:
            return False

        if open_positions >= self.settings.max_open_positions:
            return False

        if order.quantity <= Decimal(0):
            return False

        if market_state is not None:
            if not market_state.is_tradeable:
                return False

            if market_state.spread > self.settings.max_spread:
                return False

        return True

    def calculate_position_size(
        self,
        account_balance: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
        contract_size: Decimal,
        risk_fraction: Decimal | None = None,
    ) -> Decimal:
        """Calculate position size from account risk."""

        if account_balance <= Decimal(0):
            return Decimal(0)

        if entry_price <= Decimal(0):
            return Decimal(0)

        if contract_size <= Decimal(0):
            return Decimal(0)

        price_risk = abs(entry_price - stop_loss)

        if price_risk <= Decimal(0):
            return Decimal(0)

        fraction = (
            self.settings.max_risk_per_trade
            if risk_fraction is None
            else risk_fraction
        )

        if fraction <= Decimal(0):
            return Decimal(0)

        risk_amount = account_balance * fraction

        return risk_amount / (price_risk * contract_size)