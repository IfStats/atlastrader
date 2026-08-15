from datetime import UTC, datetime
from decimal import Decimal

from packages.core.enums import OrderSide, OrderStatus, OrderType, Timeframe
from packages.core.models import MarketState, Order, Signal
from packages.engine.interfaces import TradingEngine
from packages.execution.interfaces import ExecutionProvider
from packages.risk.interfaces import RiskManager
from packages.strategy.interfaces import Strategy


class DefaultTradingEngine(TradingEngine):
    """Coordinates market analysis, strategy, risk, and execution."""

    def __init__(
        self,
        *,
        strategy: Strategy,
        risk_manager: RiskManager,
        execution_provider: ExecutionProvider,
        default_quantity: Decimal = Decimal("0.01"),
    ) -> None:
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.execution_provider = execution_provider
        self.default_quantity = default_quantity

    async def process_market_state(
        self,
        market_state: MarketState,
    ) -> Order | None:
        """Generate, approve, and execute a trading signal."""

        signal = self.strategy.generate_signal(market_state)

        if signal is None:
            return None

        if not market_state.is_tradeable:
            return None

        if not await self.execution_provider.is_connected():
            raise RuntimeError("Execution provider is not connected")

        return await self.execute_signal(signal, market_state)

    async def execute_signal(
        self,
        signal: Signal,
        market_state: MarketState | None = None,
    ) -> Order | None:
        """Validate and execute an approved trading signal."""

        if not await self.execution_provider.is_connected():
            raise RuntimeError("Execution provider is not connected")

        if signal.entry_price is None:
            return None

        if market_state is None:
            market_state = self.build_market_state(
                symbol=signal.symbol,
                timeframe=Timeframe.M5,
                price=signal.entry_price,
                trend_score=1.0,
                momentum_score=1.0,
                volatility_score=0.0,
                volatility=Decimal(0),
                spread=Decimal(0),
            )

        open_positions = 0

        if not self.risk_manager.approve_signal(
            signal,
            market_state,
            open_positions,
        ):
            return None

        order = Order(
            id=self._create_order_id(),
            symbol=signal.symbol,
            side=self._signal_to_order_side(signal),
            order_type=OrderType.MARKET,
            status=OrderStatus.PENDING,
            quantity=self._default_quantity(),
            price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            signal_id=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        if not self.risk_manager.validate_order(
            order,
            market_state,
            open_positions,
        ):
            return None

        return await self.execution_provider.submit_order(order)

    async def run_once(
        self,
        market_state: MarketState,
    ) -> Order | None:
        """Run one complete strategy-to-execution cycle."""

        return await self.process_market_state(market_state)

    def build_market_state(
        self,
        *,
        symbol: str,
        timeframe: Timeframe,
        price: Decimal,
        trend_score: float,
        momentum_score: float,
        volatility_score: float,
        volatility: Decimal,
        spread: Decimal,
        is_tradeable: bool = True,
    ) -> MarketState:
        """Build a normalized market-state object for the engine."""

        return MarketState(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=datetime.now(UTC),
            price=price,
            trend_score=trend_score,
            momentum_score=momentum_score,
            volatility_score=volatility_score,
            volatility=volatility,
            spread=spread,
            is_tradeable=is_tradeable,
        )

    def _default_quantity(self) -> Decimal:
        """Return the configured default order quantity."""

        return self.default_quantity

    @staticmethod
    def _create_order_id() -> str:
        """Create a unique identifier for an engine-generated order."""

        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
        return f"engine-{timestamp}"

    @staticmethod
    def _signal_to_order_side(signal: Signal) -> OrderSide:
        """Convert a strategy signal direction into an order side."""

        return (
            OrderSide.BUY
            if signal.direction.value == "long"
            else OrderSide.SELL
        )