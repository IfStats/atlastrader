from decimal import Decimal

from packages.backtest.models import (
    BacktestConfig,
    BacktestResult,
    BacktestTrade,
)
from packages.core.enums import SignalDirection
from packages.core.models import Candle, MarketState, Signal
from packages.strategy.interfaces import Strategy


class BacktestEngine:
    """Deterministic historical backtesting engine."""

    def __init__(
        self,
        strategy: Strategy,
        config: BacktestConfig,
    ) -> None:
        self.strategy = strategy
        self.config = config

    def run(
        self,
        candles: list[Candle],
    ) -> BacktestResult:
        """Run a backtest against historical candles."""

        if not candles:
            return self._empty_result()

        balance = self.config.initial_balance
        peak_balance = balance
        max_drawdown = Decimal(0)

        trades: list[BacktestTrade] = []

        for candle in candles:
            market_state = self._build_market_state(candle)

            signal = self.strategy.generate_signal(market_state)

            if signal is None:
                continue

            if signal.symbol != self.config.symbol:
                continue

            if signal.direction not in (
                SignalDirection.LONG,
                SignalDirection.SHORT,
            ):
                continue

            trade = self._simulate_trade(candle, signal)

            if trade is None:
                continue

            trades.append(trade)

            balance += trade.profit_loss
            balance -= trade.commission

            peak_balance = max(peak_balance, balance)

            drawdown = peak_balance - balance

            max_drawdown = max(max_drawdown, drawdown)

        total_profit = balance - self.config.initial_balance

        winning_trades = sum(
            1
            for trade in trades
            if trade.profit_loss > 0
        )

        losing_trades = sum(
            1
            for trade in trades
            if trade.profit_loss < 0
        )

        return BacktestResult(
            initial_balance=self.config.initial_balance,
            ending_balance=balance,
            total_profit=total_profit,
            total_trades=len(trades),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            max_drawdown=max_drawdown,
            trades=trades,
        )

    def _build_market_state(
        self,
        candle: Candle,
    ) -> MarketState:
        """Build a minimal market state from a historical candle."""

        return MarketState(
            symbol=candle.symbol,
            timestamp=candle.timestamp,
            timeframe=candle.timeframe,
            price=candle.close,
            trend_score=1.0,
            momentum_score=1.0,
            volatility_score=1.0,
            volatility=Decimal(1),
            spread=self.config.spread,
            is_tradeable=True,
        )

    def _simulate_trade(
        self,
        candle: Candle,
        signal: Signal,
    ) -> BacktestTrade | None:
        """Simulate one signal against one historical candle."""

        if signal.entry_price is None:
            return None

        entry_price = self._apply_entry_execution_price(
            signal.entry_price,
            signal.direction,
        )

        stop_loss = signal.stop_loss
        take_profit = signal.take_profit

        exit_price: Decimal | None = None

        if signal.direction is SignalDirection.LONG:
            if stop_loss is not None and candle.low <= stop_loss:
                exit_price = self._apply_exit_execution_price(
                    stop_loss,
                    signal.direction,
                )
            elif (
                take_profit is not None
                and candle.high >= take_profit
            ):
                exit_price = self._apply_exit_execution_price(
                    take_profit,
                    signal.direction,
                )

        elif signal.direction is SignalDirection.SHORT:
            if stop_loss is not None and candle.high >= stop_loss:
                exit_price = self._apply_exit_execution_price(
                    stop_loss,
                    signal.direction,
                )
            elif (
                take_profit is not None
                and candle.low <= take_profit
            ):
                exit_price = self._apply_exit_execution_price(
                    take_profit,
                    signal.direction,
                )

        if exit_price is None:
            return None

        quantity = Decimal(1)

        if signal.direction is SignalDirection.LONG:
            profit_loss = (
                exit_price - entry_price
            ) * quantity * self.config.contract_size
        else:
            profit_loss = (
                entry_price - exit_price
            ) * quantity * self.config.contract_size

        return BacktestTrade(
            symbol=self.config.symbol,
            direction=signal.direction,
            quantity=quantity,
            entry_price=entry_price,
            exit_price=exit_price,
            profit_loss=profit_loss,
            commission=self.config.commission_per_trade,
            entry_time=signal.timestamp,
            exit_time=candle.timestamp,
        )

    def _apply_entry_execution_price(
        self,
        price: Decimal,
        direction: SignalDirection,
    ) -> Decimal:
        """Apply spread and slippage to the entry price."""

        half_spread = self.config.spread / Decimal(2)

        if direction is SignalDirection.LONG:
            return (
                price
                + half_spread
                + self.config.slippage
            )

        return (
            price
            - half_spread
            - self.config.slippage
        )

    def _apply_exit_execution_price(
        self,
        price: Decimal,
        direction: SignalDirection,
    ) -> Decimal:
        """Apply spread and slippage to the exit price."""

        half_spread = self.config.spread / Decimal(2)

        if direction is SignalDirection.LONG:
            return (
                price
                - half_spread
                - self.config.slippage
            )

        return (
            price
            + half_spread
            + self.config.slippage
        )

    def _empty_result(self) -> BacktestResult:
        """Return an empty backtest result."""

        return BacktestResult(
            initial_balance=self.config.initial_balance,
            ending_balance=self.config.initial_balance,
            total_profit=Decimal(0),
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            max_drawdown=Decimal(0),
            trades=[],
        )