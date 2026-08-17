from decimal import Decimal

from packages.backtest.models import BacktestConfig, BacktestResult, BacktestTrade
from packages.core.enums import SignalDirection, Timeframe
from packages.core.models import Candle, MarketState, Signal
from packages.risk.interfaces import RiskManager
from packages.strategy.interfaces import Strategy


class BacktestEngine:
    """Historical simulation engine for AtlasTrader strategies."""

    def __init__(
        self,
        strategy: Strategy,
        config: BacktestConfig,
        risk_manager: RiskManager | None = None,
    ) -> None:
        self.strategy = strategy
        self.config = config
        self.risk_manager = risk_manager

    def run(self, candles: list[Candle]) -> BacktestResult:
        """Run the strategy against historical candles."""

        if not candles:
            return self._build_result([], self.config.initial_balance)

        balance = self.config.initial_balance
        peak_balance = balance
        max_drawdown = Decimal(0)
        trades: list[BacktestTrade] = []

        for candle in candles:
            market_state = self._build_market_state(candle)
            signal = self.strategy.generate_signal(market_state)

            if signal is None:
                continue

            if self.risk_manager is not None and not self.risk_manager.approve_signal(
                signal,
                market_state,
            ):
                continue

            trade = self._execute_signal(signal, candle)

            if trade is None:
                continue

            balance += trade.profit_loss
            balance -= trade.commission
            trades.append(trade)

            peak_balance = max(peak_balance, balance)

            drawdown = peak_balance - balance
            max_drawdown = max(max_drawdown, drawdown)

        return self._build_result(trades, balance, max_drawdown)

    def _execute_signal(
        self,
        signal: Signal,
        candle: Candle,
    ) -> BacktestTrade | None:
        """Simulate execution of a signal."""

        if signal.entry_price is None:
            return None

        if signal.stop_loss is None:
            return None

        if signal.take_profit is None:
            return None

        quantity = Decimal(1)

        entry_price = self._apply_slippage(
            signal.entry_price,
            signal.direction,
        )

        exit_price = self._resolve_exit_price(
            signal,
            candle,
        )

        if exit_price is None:
            return None

        exit_price = self._apply_slippage(
            exit_price,
            SignalDirection.SHORT
            if signal.direction == SignalDirection.LONG
            else SignalDirection.LONG,
        )

        if signal.direction == SignalDirection.LONG:
            profit_loss = (exit_price - entry_price) * quantity
        else:
            profit_loss = (entry_price - exit_price) * quantity

        commission = self.config.commission_per_trade

        return BacktestTrade(
            symbol=signal.symbol,
            direction=signal.direction,
            quantity=quantity,
            entry_price=entry_price,
            exit_price=exit_price,
            profit_loss=profit_loss,
            commission=commission,
            entry_time=signal.timestamp,
            exit_time=candle.timestamp,
        )

    def _resolve_exit_price(
        self,
        signal: Signal,
        candle: Candle,
    ) -> Decimal | None:
        """Determine whether stop-loss or take-profit was reached."""

        if signal.stop_loss is None or signal.take_profit is None:
            return None

        if signal.direction == SignalDirection.LONG:
            if candle.low <= signal.stop_loss:
                return signal.stop_loss

            if candle.high >= signal.take_profit:
                return signal.take_profit
        else:
            if candle.high >= signal.stop_loss:
                return signal.stop_loss

            if candle.low <= signal.take_profit:
                return signal.take_profit

        return None

    def _apply_slippage(
        self,
        price: Decimal,
        direction: SignalDirection,
    ) -> Decimal:
        """Apply configured slippage to an execution price."""

        if self.config.slippage == 0:
            return price

        if direction == SignalDirection.LONG:
            return price + self.config.slippage

        return price - self.config.slippage

    def _build_result(
        self,
        trades: list[BacktestTrade],
        ending_balance: Decimal,
        max_drawdown: Decimal = Decimal(0),
    ) -> BacktestResult:
        """Build aggregate backtest statistics."""

        total_profit = sum(
            (trade.profit_loss - trade.commission for trade in trades),
            Decimal(0),
        )

        winning_trades = sum(
            1
            for trade in trades
            if trade.profit_loss - trade.commission > 0
        )

        losing_trades = sum(
            1
            for trade in trades
            if trade.profit_loss - trade.commission < 0
        )

        return BacktestResult(
            initial_balance=self.config.initial_balance,
            ending_balance=ending_balance,
            total_profit=total_profit,
            total_trades=len(trades),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            max_drawdown=max_drawdown,
            trades=trades,
        )

    def _build_market_state(self, candle: Candle) -> MarketState:
        """Convert a historical candle into a market state."""

        return MarketState(
            symbol=self.config.symbol,
            timeframe=Timeframe.M5,
            timestamp=candle.timestamp,
            price=candle.close,
            trend_score=1.0,
            momentum_score=1.0,
            volatility_score=1.0,
            volatility=candle.high - candle.low,
            spread=Decimal(0),
            is_tradeable=True,
        )