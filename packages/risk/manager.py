from decimal import Decimal

from packages.core.config import RiskSettings
from packages.core.models import MarketState, Order, Signal
from packages.portfolio.models import PortfolioSnapshot
from packages.risk.interfaces import RiskManager


class DefaultRiskManager(RiskManager):
    """Default risk-management implementation for AtlasTrader."""

    _DEFAULT_ACCOUNT_EQUITY = Decimal(10000)

    def __init__(self, settings: RiskSettings) -> None:
        self.settings = settings

    def _get_equity(
        self,
        portfolio: PortfolioSnapshot | None,
    ) -> Decimal:
        """Return current account equity, with a test/default fallback."""

        if portfolio is not None:
            return portfolio.equity

        return self._DEFAULT_ACCOUNT_EQUITY

    def can_trade(
        self,
        daily_loss: Decimal,
        portfolio: PortfolioSnapshot | None = None,
        *,
        open_positions: int | None = None,
        current_exposure: Decimal | None = None,
    ) -> bool:
        """Determine whether trading is currently permitted."""

        if not self.settings.trading_enabled:
            return False

        account_equity = self._get_equity(portfolio)

        max_daily_loss = (
            account_equity
            * self.settings.max_daily_loss
        )

        if daily_loss <= -max_daily_loss:
            return False

        if portfolio is not None:
            open_positions = portfolio.open_positions
            current_exposure = portfolio.total_exposure

        if open_positions is None:
            open_positions = 0

        if current_exposure is None:
            current_exposure = Decimal(0)

        if open_positions >= self.settings.max_open_positions:
            return False

        max_exposure = (
            account_equity
            * self.settings.max_portfolio_exposure
        )

        return current_exposure <= max_exposure

    def approve_signal(
        self,
        signal: Signal,
        market_state: MarketState,
        portfolio: PortfolioSnapshot | None = None,
        *,
        open_positions: int | None = None,
        current_exposure: Decimal | None = None,
    ) -> bool:
        """Determine whether a signal passes risk controls."""

        if not self.settings.trading_enabled:
            return False

        if not market_state.is_tradeable:
            return False

        if signal.symbol != market_state.symbol:
            return False

        if signal.entry_price is None:
            return False

        if signal.stop_loss is None:
            return False

        if signal.take_profit is None:
            return False

        if (
            portfolio is not None
            and signal.symbol in portfolio.open_symbols
        ):
            return False

        if market_state.spread > self.settings.max_spread:
            return False

        account_equity = self._get_equity(portfolio)

        if portfolio is not None:
            open_positions = portfolio.open_positions
            current_exposure = portfolio.total_exposure

        if open_positions is None:
            open_positions = 0

        if current_exposure is None:
            current_exposure = Decimal(0)

        if open_positions >= self.settings.max_open_positions:
            return False

        max_exposure = (
            account_equity
            * self.settings.max_portfolio_exposure
        )

        if current_exposure > max_exposure:
            return False

        return (
            signal.risk_reward_ratio is not None
            and Decimal(str(signal.risk_reward_ratio))
            >= self.settings.min_risk_reward_ratio
        )

    def validate_order(
        self,
        order: Order,
        portfolio: PortfolioSnapshot | None = None,
        market_state: MarketState | None = None,
        *,
        open_positions: int | None = None,
        current_exposure: Decimal | None = None,
    ) -> bool:
        """Determine whether an order passes risk controls."""

        if not self.settings.trading_enabled:
            return False

        if order.quantity <= Decimal(0):
            return False

        account_equity = self._get_equity(portfolio)

        if portfolio is not None:
            open_positions = portfolio.open_positions
            current_exposure = portfolio.total_exposure

        if open_positions is None:
            open_positions = 0

        if current_exposure is None:
            current_exposure = Decimal(0)

        if open_positions >= self.settings.max_open_positions:
            return False

        max_exposure = (
            account_equity
            * self.settings.max_portfolio_exposure
        )

        order_exposure = Decimal(0)

        if order.price is not None:
            order_exposure = order.price * order.quantity

        if current_exposure + order_exposure > max_exposure:
            return False

        if market_state is not None:
            if not market_state.is_tradeable:
                return False

            if market_state.spread > self.settings.max_spread:
                return False

        return True