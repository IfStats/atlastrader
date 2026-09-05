
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from uuid import uuid4

from packages.core.config import RiskSettings
from packages.core.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    SignalDirection,
)
from packages.core.models import Instrument, MarketState, Order, Signal
from packages.core.trading_journal import TradeDecision
from packages.engine.autonomous_decision import (
    AutonomousDecisionEngine,
)
from packages.engine.interfaces import TradingEngine
from packages.engine.journal import TradeJournal
from packages.engine.market_context import MarketContext
from packages.execution.interfaces import ExecutionProvider
from packages.portfolio.instrument_registry import InstrumentRegistry
from packages.portfolio.position_manager import PositionManager
from packages.portfolio.service import PortfolioService
from packages.risk.interfaces import RiskManager
from packages.risk.position_sizer import PositionSizer
from packages.strategy.service import StrategyService


class MarketStateProvider(Protocol):
    """Interface required by the trading engine for normalized market state."""

    async def get_market_state(self, symbol: str) -> MarketState:
        """Return the normalized market state for a symbol."""
        ...

class MarketContextProvider(Protocol):
    """Interface required by the engine for autonomous market context."""

    async def get_market_context(self, symbol: str) -> MarketContext:
        """Return combined technical and intelligence context for a symbol."""
        ...

class DefaultTradingEngine(TradingEngine):
    """Coordinates market analysis, risk, sizing, execution, and portfolio state."""

    def __init__(
        self,
        *,
        strategy_service: StrategyService,
        risk_manager: RiskManager,
        execution_provider: ExecutionProvider,
        position_sizer: PositionSizer,
        risk_settings: RiskSettings,
        portfolio: PortfolioService,
        position_manager: PositionManager | None = None,
        market_data_provider: MarketStateProvider | None = None,
        market_context_provider: MarketContextProvider | None = None,
        autonomous_decision_engine: AutonomousDecisionEngine | None = None,
        instrument_registry: InstrumentRegistry | None = None,
        journal: TradeJournal | None = None,
    ) -> None:
        self.strategy_service = strategy_service
        self.risk_manager = risk_manager
        self.execution_provider = execution_provider
        self.position_sizer = position_sizer
        self.risk_settings = risk_settings
        self.portfolio = portfolio
        self.position_manager = position_manager or PositionManager(
            execution_provider=execution_provider,
            portfolio=portfolio,
        )
        self.market_data_provider = market_data_provider
        self.market_context_provider = market_context_provider
        self.autonomous_decision_engine = (
            autonomous_decision_engine or AutonomousDecisionEngine()
        )
        self.instrument_registry = instrument_registry
        self.journal = journal

    async def process_symbol(
        self,
        symbol: str,
    ) -> Order | None:
        """Fetch current market state for a symbol and process it."""
        if self.market_data_provider is None:
            raise RuntimeError(
                "Market data provider is required to process a symbol"
            )

        market_state = await self.market_data_provider.get_market_state(symbol)

        return await self.process_market_state(market_state)

    async def process_autonomous_symbol(
        self,
        symbol: str,
) -> Order | None:
     """Evaluate a symbol through the autonomous decision pipeline."""

     if self.market_context_provider is None:
        raise RuntimeError(
            "Market context provider is required to process a symbol "
            "autonomously"
        )

     context = await self.market_context_provider.get_market_context(symbol)
     autonomous_decision = self.autonomous_decision_engine.evaluate(context)

     if not autonomous_decision.approved:
        return None

     signal = self.strategy_service.select_signal(context.market_state)

     if signal is None:
        return None

     if signal.direction is not autonomous_decision.decision:
        return None

     return await self.execute_signal(
        signal,
        context.market_state,
    )

    async def process_market_state(
        self,
        market_state: MarketState,
    ) -> Order | None:
        """Generate, validate, size, and execute the best signal."""
        if not market_state.is_tradeable:
            return None

        signal = self.strategy_service.select_signal(market_state)

        if signal is None:
            return None

        return await self.execute_signal(
            signal,
            market_state,
        )

    async def execute_signal(
        self,
        signal: Signal,
        market_state: MarketState | None = None,
    ) -> Order | None:
        """Validate a signal, calculate size, and execute the resulting order."""
        if market_state is None:
            if self.market_data_provider is None:
                raise RuntimeError(
                    "Market state is required when no market data provider "
                    "is configured"
                )

            market_state = await self.market_data_provider.get_market_state(
                signal.symbol
            )

        decision_id = f"decision-{uuid4().hex}"

        if not self.risk_manager.approve_signal(
            signal,
            market_state,
            self.portfolio.snapshot(),
        ):
            self._record_decision(
                signal=signal,
                market_state=market_state,
                decision=signal.direction,
                status="rejected",
                rejection_reasons=["risk_manager_rejected_signal"],
                decision_id=decision_id,
            )
            return None

        if signal.entry_price is None:
            self._record_decision(
                signal=signal,
                market_state=market_state,
                decision=SignalDirection.FLAT,
                status="rejected",
                rejection_reasons=["missing_entry_price"],
                decision_id=decision_id,
            )
            return None

        if signal.stop_loss is None:
            self._record_decision(
                signal=signal,
                market_state=market_state,
                decision=signal.direction,
                status="rejected",
                rejection_reasons=["missing_stop_loss"],
                decision_id=decision_id,
            )
            return None

        instrument = await self._get_instrument(signal.symbol)
        portfolio_snapshot = self.portfolio.snapshot()

        quantity = self.position_sizer.calculate_volume(
            equity=portfolio_snapshot.equity,
            risk_percent=(
                self.risk_settings.max_risk_per_trade
                * Decimal(100)
            ),
            entry_price=signal.entry_price,
            stop_loss_price=signal.stop_loss,
            instrument=instrument,
        )

        if quantity <= Decimal(0):
            self._record_decision(
                signal=signal,
                market_state=market_state,
                decision=signal.direction,
                status="rejected",
                rejection_reasons=["position_size_zero"],
                decision_id=decision_id,
            )
            return None

        order = self._build_order(
            signal=signal,
            quantity=quantity,
        )

        approved = self.risk_manager.validate_order(
            order,
            self.portfolio.snapshot(),
            market_state,
        )

        if not approved:
            rejected_order = order.model_copy(
                update={
                    "status": OrderStatus.REJECTED,
                    "updated_at": datetime.now(UTC),
                }
            )

            self._record_decision(
                signal=signal,
                market_state=market_state,
                decision=signal.direction,
                status="rejected",
                rejection_reasons=["risk_manager_rejected_order"],
                requested_quantity=quantity,
                decision_id=decision_id,
                order_id=rejected_order.id,
            )

            return rejected_order

        self._record_decision(
            signal=signal,
            market_state=market_state,
            decision=signal.direction,
            status="approved",
            requested_quantity=quantity,
            decision_id=decision_id,
            order_id=order.id,
        )

        executed_order = await self.execution_provider.submit_order(order)

        if executed_order.status is OrderStatus.FILLED:
            if self.position_manager.portfolio is not self.portfolio:
                self.position_manager.portfolio = self.portfolio

            self.position_manager.record_filled_order(
                executed_order,
            )

        return executed_order

    async def _get_instrument(
        self,
        symbol: str,
    ) -> Instrument:
        """Resolve instrument metadata from the registry or execution venue."""
        if self.instrument_registry is not None:
            return self.instrument_registry.get(symbol)

        return await self.execution_provider.get_instrument(symbol)

    def _record_decision(
        self,
        *,
        signal: Signal,
        market_state: MarketState,
        decision: SignalDirection,
        status: str,
        rejection_reasons: list[str] | None = None,
        decision_id: str,
        requested_quantity: Decimal | None = None,
        order_id: str | None = None,
    ) -> None:
        """Record a signal-backed trading decision when journaling is enabled."""
        if self.journal is None:
            return

        now = datetime.now(UTC)

        journal_entry = TradeDecision(
            id=decision_id,
            symbol=signal.symbol,
            direction=signal.direction,
            strategy=signal.strategy,
            timeframe=signal.timeframe,
            decision=decision,
            status=status,
            timestamp=signal.timestamp,
            signal_score=signal.score,
            confidence=signal.score / 100,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            risk_reward_ratio=(
                Decimal(str(signal.risk_reward_ratio))
                if signal.risk_reward_ratio is not None
                else None
            ),
            requested_quantity=requested_quantity,
            rationale=list(signal.rationale),
            rejection_reasons=list(rejection_reasons or []),
            market_state={
                "price": str(market_state.price),
                "trend_score": market_state.trend_score,
                "momentum_score": market_state.momentum_score,
                "volatility_score": market_state.volatility_score,
                "volatility": str(market_state.volatility),
                "spread": str(market_state.spread),
                "market_status": market_state.market_status.value,
                "session": market_state.session,
                "is_tradeable": market_state.is_tradeable,
            },
            order_id=order_id,
            created_at=now,
            updated_at=now,
        )

        self.journal.record_decision(journal_entry)

    @staticmethod
    def _build_order(
        *,
        signal: Signal,
        quantity: Decimal,
    ) -> Order:
        """Convert an approved signal into an executable order."""
        if signal.direction is SignalDirection.LONG:
            side = OrderSide.BUY
        elif signal.direction is SignalDirection.SHORT:
            side = OrderSide.SELL
        else:
            raise ValueError("FLAT signals cannot be converted into orders")

        now = datetime.now(UTC)

        return Order(
            id=f"engine-{uuid4().hex}",
            symbol=signal.symbol,
            side=side,
            order_type=OrderType.MARKET,
            status=OrderStatus.PENDING,
            quantity=quantity,
            price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            signal_id=None,
            created_at=now,
            updated_at=now,
        )