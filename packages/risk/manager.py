from decimal import Decimal

from packages.core.config import RiskSettings
from packages.core.models import MarketState, Order, Position, Signal
from packages.risk.interfaces import RiskManager


class DefaultRiskManager(RiskManager):
    """Default deterministic risk engine for AtlasTrader."""

    def __init__(self, settings: RiskSettings | None = None) -> None:
        self._settings = settings or RiskSettings()

    @property
    def settings(self) -> RiskSettings:
        return self._settings

    def approve_signal(
        self,
        signal: Signal,
        market_state: MarketState,
        open_positions: list[Position],
    ) -> bool:
        """Apply risk controls before a signal can become executable."""

        if not self.can_trade(Decimal(0)):
            return False

        if not market_state.is_tradeable:
            return False

        if market_state.spread > self.settings.max_spread:
            return False

        if signal.risk_reward_ratio is None:
            return False

        if Decimal(str(signal.risk_reward_ratio)) < self.settings.min_risk_reward_ratio:
            return False

        if len(open_positions) >= self.settings.max_open_positions:
            return False

        return not (signal.entry_price is None or signal.stop_loss is None)

    def validate_order(
        self,
        order: Order,
        market_state: MarketState,
        open_positions: list[Position],
    ) -> bool:
        """Apply risk controls immediately before order submission."""

        if not self.settings.trading_enabled:
            return False

        if not market_state.is_tradeable:
            return False

        if market_state.spread > self.settings.max_spread:
            return False

        if len(open_positions) >= self.settings.max_open_positions:
            return False

        return not order.quantity <= Decimal(0)

    def calculate_position_size(
        self,
        account_balance: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
        contract_size: Decimal,
        risk_fraction: Decimal | None = None,
    ) -> Decimal:
        """Calculate quantity using fixed fractional risk.

        Formula:

            risk_amount = account_balance * risk_fraction

            stop_distance = abs(entry_price - stop_loss)

            position_size =
                risk_amount / (stop_distance * contract_size)
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

        risk_fraction = (
            risk_fraction
            if risk_fraction is not None
            else self.settings.max_risk_per_trade
        )

        if risk_fraction <= Decimal(0):
            raise ValueError("risk_fraction must be greater than zero")

        stop_distance = abs(entry_price - stop_loss)
        risk_amount = account_balance * risk_fraction

        return risk_amount / (stop_distance * contract_size)

    def can_trade(self, daily_pnl: Decimal) -> bool:
        """Return whether the account is within its daily loss limit."""

        if not self.settings.trading_enabled:
            return False

        daily_loss_limit = -abs(
            Decimal(str(self.settings.max_daily_loss))
        )

        return daily_pnl > daily_loss_limit