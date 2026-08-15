from decimal import Decimal

from packages.core.config import RiskSettings
from packages.core.models import MarketState, Order, Signal
from packages.risk.interfaces import RiskManager


class DefaultRiskManager(RiskManager):
    """Default implementation of AtlasTrader risk controls."""

    REFERENCE_ACCOUNT_BALANCE = Decimal(10000)

    def __init__(self, settings: RiskSettings) -> None:
        self.settings = settings

    def can_trade(
        self,
        daily_loss: Decimal,
        open_positions: int = 0,
    ) -> bool:
        """Return whether new trading activity is currently permitted."""

        if not self.settings.trading_enabled:
            return False

        daily_loss_amount = abs(daily_loss)
        max_daily_loss_amount = (
            self.REFERENCE_ACCOUNT_BALANCE
            * self.settings.max_daily_loss
        )

        if daily_loss_amount >= max_daily_loss_amount:
            return False

        return open_positions < self.settings.max_open_positions

    def approve_signal(
        self,
        signal: Signal,
        market_state: MarketState,
        open_positions: int = 0,
    ) -> bool:
        """Apply risk controls before a signal can become executable."""

        if not self.settings.trading_enabled:
            return False

        if not market_state.is_tradeable:
            return False

        if open_positions >= self.settings.max_open_positions:
            return False

        if signal.entry_price is None or signal.stop_loss is None:
            return False

        if signal.risk_reward_ratio is None:
            return False

        if signal.risk_reward_ratio < self.settings.min_risk_reward_ratio:
            return False

        return not market_state.spread > self.settings.max_spread

    def validate_order(
        self,
        order: Order,
        market_state: MarketState | None = None,
        open_positions: int = 0,
    ) -> bool:
        """Validate an order against current risk controls."""

        if not self.settings.trading_enabled:
            return False

        if open_positions >= self.settings.max_open_positions:
            return False

        if order.quantity <= Decimal(0):
            return False

        if market_state is not None:
            if not market_state.is_tradeable:
                return False

            return not market_state.spread > self.settings.max_spread

        return True

    def calculate_position_size(
        self,
        account_balance: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
        contract_size: Decimal,
        risk_fraction: Decimal | None = None,
    ) -> Decimal:
        """
        Calculate position size from account risk and stop-loss distance.

        Formula:
            risk_amount = account_balance * risk_fraction
            price_risk = abs(entry_price - stop_loss)
            position_size = risk_amount / (price_risk * contract_size)
        """

        if account_balance <= Decimal(0):
            raise ValueError("account_balance must be greater than zero")

        if entry_price <= Decimal(0):
            raise ValueError("entry_price must be greater than zero")

        if stop_loss <= Decimal(0):
            raise ValueError("stop_loss must be greater than zero")

        if contract_size <= Decimal(0):
            raise ValueError("contract_size must be greater than zero")

        if entry_price == stop_loss:
            raise ValueError("entry_price and stop_loss must be different")

        if risk_fraction is None:
            risk_fraction = self.settings.max_risk_per_trade

        if risk_fraction <= Decimal(0):
            raise ValueError("risk_fraction must be greater than zero")

        risk_amount = account_balance * risk_fraction
        price_risk = abs(entry_price - stop_loss)

        return risk_amount / (price_risk * contract_size)