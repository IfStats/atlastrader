from datetime import UTC, datetime
from decimal import Decimal

from packages.backtest.engine import BacktestEngine
from packages.backtest.models import BacktestConfig
from packages.core.enums import SignalDirection, StrategyType, Timeframe
from packages.core.models import Candle, Signal


class FixedSignalStrategy:
    """Test strategy that returns a predetermined signal."""

    def __init__(self, signal: Signal) -> None:
        self.signal = signal

    def generate_signal(self, market_state):  # type: ignore[no-untyped-def]
        return self.signal


def make_candle(
    *,
    high: Decimal,
    low: Decimal,
    close: Decimal = Decimal(100),
) -> Candle:
    timestamp = datetime.now(UTC)

    return Candle(
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        timestamp=timestamp,
        open=Decimal(100),
        high=high,
        low=low,
        close=close,
        volume=Decimal(100),
    )


def make_signal(
    *,
    direction: SignalDirection = SignalDirection.LONG,
) -> Signal:
    if direction == SignalDirection.LONG:
        stop_loss = Decimal(95)
        take_profit = Decimal(110)
    else:
        stop_loss = Decimal(110)
        take_profit = Decimal(90)

    return Signal(
        symbol="XAUUSD",
        direction=direction,
        strategy=StrategyType.MOMENTUM,
        score=90,
        timestamp=datetime.now(UTC),
        timeframe=Timeframe.M5,
        entry_price=Decimal(100),
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward_ratio=Decimal(2),
    )


def make_config(**overrides) -> BacktestConfig:  # type: ignore[no-untyped-def]
    values = {
        "symbol": "XAUUSD",
        "initial_balance": Decimal(10000),
    }
    values.update(overrides)
    return BacktestConfig(**values)


def test_backtest_returns_empty_result_for_empty_candles() -> None:
    engine = BacktestEngine(
        FixedSignalStrategy(make_signal()),
        make_config(),
    )

    result = engine.run([])

    assert result.total_trades == 0
    assert result.total_profit == Decimal(0)
    assert result.ending_balance == Decimal(10000)
    assert result.max_drawdown == Decimal(0)


def test_long_trade_closes_at_take_profit() -> None:
    engine = BacktestEngine(
        FixedSignalStrategy(make_signal()),
        make_config(),
    )

    result = engine.run(
        [
            make_candle(
                high=Decimal(111),
                low=Decimal(99),
            )
        ]
    )

    assert result.total_trades == 1
    assert result.winning_trades == 1
    assert result.losing_trades == 0
    assert result.total_profit == Decimal(10)
    assert result.ending_balance == Decimal(10010)


def test_long_trade_closes_at_stop_loss() -> None:
    engine = BacktestEngine(
        FixedSignalStrategy(make_signal()),
        make_config(),
    )

    result = engine.run(
        [
            make_candle(
                high=Decimal(101),
                low=Decimal(94),
            )
        ]
    )

    assert result.total_trades == 1
    assert result.winning_trades == 0
    assert result.losing_trades == 1
    assert result.total_profit == Decimal(-5)
    assert result.ending_balance == Decimal(9995)
    assert result.max_drawdown == Decimal(5)


def test_commission_is_included_in_backtest_profit() -> None:
    engine = BacktestEngine(
        FixedSignalStrategy(make_signal()),
        make_config(
            commission_per_trade=Decimal(2),
        ),
    )

    result = engine.run(
        [
            make_candle(
                high=Decimal(111),
                low=Decimal(99),
            )
        ]
    )

    assert result.total_profit == Decimal(8)
    assert result.ending_balance == Decimal(10008)


def test_slippage_changes_execution_price() -> None:
    engine = BacktestEngine(
        FixedSignalStrategy(make_signal()),
        make_config(
            slippage=Decimal(1),
        ),
    )

    result = engine.run(
        [
            make_candle(
                high=Decimal(111),
                low=Decimal(99),
            )
        ]
    )

    trade = result.trades[0]

    assert trade.entry_price == Decimal(101)
    assert trade.exit_price == Decimal(109)
    assert trade.profit_loss == Decimal(8)


def test_short_trade_closes_at_take_profit() -> None:
    engine = BacktestEngine(
        FixedSignalStrategy(
            make_signal(direction=SignalDirection.SHORT)
        ),
        make_config(),
    )

    result = engine.run(
        [
            make_candle(
                high=Decimal(101),
                low=Decimal(89),
            )
        ]
    )

    assert result.total_trades == 1
    assert result.winning_trades == 1
    assert result.losing_trades == 0
    assert result.total_profit == Decimal(10)
    assert result.ending_balance == Decimal(10010)


def test_backtest_calculates_return_percentage() -> None:
    engine = BacktestEngine(
        FixedSignalStrategy(make_signal()),
        make_config(),
    )

    result = engine.run(
        [
            make_candle(
                high=Decimal(111),
                low=Decimal(99),
            )
        ]
    )

    assert result.return_percentage == Decimal("0.1")


def test_backtest_calculates_win_rate() -> None:
    engine = BacktestEngine(
        FixedSignalStrategy(make_signal()),
        make_config(),
    )

    result = engine.run(
        [
            make_candle(
                high=Decimal(111),
                low=Decimal(99),
            )
        ]
    )

    assert result.win_rate == Decimal(100)