from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from packages.core.config import MT5Settings, RiskSettings, RuntimeSettings
from packages.core.enums import MarketStatus, OrderSide, OrderType, Timeframe
from packages.core.models import MarketState, Order
from packages.execution.mt5 import MT5ExecutionProvider
from packages.execution.preflight import MT5Preflight
from packages.execution.service import ExecutionService
from packages.market_data.mt5 import MT5MarketDataProvider
from packages.portfolio.models import PortfolioSnapshot
from packages.risk.manager import DefaultRiskManager
from packages.runtime.factory import create_runtime
from packages.runtime.service import TradingRuntime

DEMO_SYMBOL = "XAUUSD"
DEMO_VOLUME = Decimal("0.01")
DEMO_STOP_DISTANCE = Decimal("5.00")
DEMO_TAKE_PROFIT_DISTANCE = Decimal("10.00")


async def create_mt5_providers() -> tuple[
    MT5ExecutionProvider,
    MT5MarketDataProvider,
]:
    """Create configured MT5 execution and market-data providers."""

    mt5_settings = MT5Settings()

    execution_provider = MT5ExecutionProvider(
        login=mt5_settings.login,
        password=mt5_settings.password,
        server=mt5_settings.server,
        path=mt5_settings.path,
    )

    market_data_provider = MT5MarketDataProvider()

    return execution_provider, market_data_provider


async def run_preflight() -> int:
    """Run the read-only MT5 readiness assessment."""

    runtime_settings = RuntimeSettings()

    (
        execution_provider,
        market_data_provider,
    ) = await create_mt5_providers()

    try:
        print("Connecting to MT5...")

        await execution_provider.connect()
        await market_data_provider.connect()

        preflight = MT5Preflight(
            execution_provider=execution_provider,
            market_data_provider=market_data_provider,
            symbols=runtime_settings.get_symbols(),
        )

        result = await preflight.run()

        print()
        print("=== MT5 PREFLIGHT ===")
        print()

        print("Terminal:")
        print(f"  connected: {result.terminal.connected}")
        print(f"  trade_allowed: {result.terminal.trade_allowed}")
        print(
            "  tradeapi_disabled: "
            f"{result.terminal.tradeapi_disabled}"
        )
        print(f"  build: {result.terminal.build}")
        print(f"  name: {result.terminal.name}")

        print()
        print("Account:")
        print(f"  login: {result.account.login}")
        print(f"  server: {result.account.server}")
        print(f"  currency: {result.account.currency}")
        print(f"  balance: {result.account.balance}")
        print(f"  equity: {result.account.equity}")
        print(f"  margin: {result.account.margin}")
        print(f"  free_margin: {result.account.free_margin}")
        print(f"  leverage: {result.account.leverage}")
        print(
            "  trade_allowed: "
            f"{result.account.trade_allowed}"
        )
        print(
            "  trade_expert: "
            f"{result.account.trade_expert}"
        )

        print()
        print("Instruments:")

        for symbol, instrument in result.instruments.items():
            print(
                f"  {symbol}: "
                f"enabled={instrument.enabled}, "
                f"min={instrument.min_volume}, "
                f"max={instrument.max_volume}, "
                f"step={instrument.volume_step}"
            )

        print()
        print("Existing positions:")

        if result.positions:
            for position in result.positions:
                print(
                    f"  {position.symbol}: "
                    f"{position.side.value} "
                    f"{position.quantity} "
                    f"entry={position.entry_price}"
                )
        else:
            print("  none")

        print()
        print("Quote status:")

        for symbol, valid in result.quote_status.items():
            print(f"  {symbol}: {valid}")

        print()
        print("Checks:")

        for name, passed in result.checks.items():
            check_status = "PASS" if passed else "FAIL"
            print(f"  [{check_status}] {name}")

        print()

        if result.blockers:
            print("Blockers:")

            for blocker in result.blockers:
                print(f"  - {blocker}")

            print()
            print("PREFLIGHT: BLOCKED")
            return 1

        print("PREFLIGHT: READY")
        return 0

    finally:
        await market_data_provider.disconnect()
        await execution_provider.disconnect()


def parse_side(value: str) -> OrderSide:
    """Parse an explicit demo-order direction."""

    normalized = value.strip().upper()

    if normalized == "BUY":
        return OrderSide.BUY

    if normalized == "SELL":
        return OrderSide.SELL

    raise argparse.ArgumentTypeError(
        "side must be BUY or SELL"
    )


def build_demo_order(
    *,
    side: OrderSide,
    price: Decimal,
) -> Order:
    """Build the single controlled demo order."""

    if side is OrderSide.BUY:
        stop_loss = price - DEMO_STOP_DISTANCE
        take_profit = price + DEMO_TAKE_PROFIT_DISTANCE
    else:
        stop_loss = price + DEMO_STOP_DISTANCE
        take_profit = price - DEMO_TAKE_PROFIT_DISTANCE

    now = datetime.now(UTC)

    return Order(
        id=str(uuid4()),
        symbol=DEMO_SYMBOL,
        side=side,
        order_type=OrderType.MARKET,
        quantity=DEMO_VOLUME,
        price=price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        created_at=now,
        updated_at=now,
    )


async def run_demo_order(
    *,
    side: OrderSide,
) -> int:
    """Submit exactly one controlled XAUUSD demo order."""

    risk_settings = RiskSettings()

    if not risk_settings.trading_enabled:
        print("DEMO ORDER: BLOCKED")
        print("AtlasTrader trading is disabled.")
        return 1

    (
        execution_provider,
        market_data_provider,
    ) = await create_mt5_providers()

    try:
        print("Connecting to MT5...")
        await execution_provider.connect()
        await market_data_provider.connect()

        print()
        print("Running preflight...")

        preflight = MT5Preflight(
            execution_provider=execution_provider,
            market_data_provider=market_data_provider,
            symbols=[DEMO_SYMBOL],
        )

        preflight_result = await preflight.run()

        if not preflight_result.ready:
            print()
            print("DEMO ORDER: BLOCKED")
            print("Preflight failed:")

            for blocker in preflight_result.blockers:
                print(f"  - {blocker}")

            return 1

        account = await execution_provider.get_account_snapshot()

        existing_position = await execution_provider.get_position(
            DEMO_SYMBOL
        )

        if existing_position is not None:
            print()
            print("DEMO ORDER: BLOCKED")
            print(
                f"An existing {DEMO_SYMBOL} position is present. "
                "No new order will be submitted."
            )
            return 1

        quote = await market_data_provider.get_quote(DEMO_SYMBOL)

        if side is OrderSide.BUY:
            execution_price = quote.ask
        else:
            execution_price = quote.bid

        market_state = MarketState(
            symbol=DEMO_SYMBOL,
            timestamp=quote.timestamp,
            timeframe=Timeframe.M5,
            price=execution_price,
            trend_score=0.0,
            momentum_score=0.0,
            volatility_score=0.0,
            volatility=Decimal(0),
            spread=quote.spread,
            market_status=MarketStatus.OPEN,
            is_tradeable=True,
        )

        order = build_demo_order(
            side=side,
            price=execution_price,
        )

        portfolio = PortfolioSnapshot(
            balance=account.balance,
            equity=account.equity,
            open_positions=len(
                await execution_provider.get_positions()
            ),
            total_exposure=Decimal(0),
        )

        risk_manager = DefaultRiskManager(risk_settings)

        execution_service = ExecutionService(
            provider=execution_provider,
            risk_manager=risk_manager,
            portfolio=portfolio,
        )

        print()
        print("=== DEMO ORDER ===")
        print()
        print(f"  symbol: {order.symbol}")
        print(f"  side: {order.side.value}")
        print(f"  type: {order.order_type.value}")
        print(f"  quantity: {order.quantity}")
        print(f"  price: {order.price}")
        print(f"  stop_loss: {order.stop_loss}")
        print(f"  take_profit: {order.take_profit}")
        print(f"  spread: {market_state.spread}")
        print()

        print("Running RiskManager and ExecutionSafetyGate...")

        result = await execution_service.submit_order(
            order,
            market_state=market_state,
        )

        if result.status.value != "filled":
            print()
            print("DEMO ORDER: REJECTED")
            print(f"  status: {result.status.value}")
            return 1

        print()
        print("DEMO ORDER: FILLED")
        print(f"  order_id: {result.id}")
        print(f"  symbol: {result.symbol}")
        print(f"  side: {result.side.value}")
        print(f"  quantity: {result.quantity}")
        print(f"  execution_price: {result.price}")

        print()
        print("Reconciling XAUUSD position...")

        position = await execution_provider.get_position(
            DEMO_SYMBOL
        )

        if position is None:
            print()
            print(
                "WARNING: Broker reported execution, but "
                "XAUUSD position was not found during reconciliation."
            )
            return 2

        print()
        print("=== POSITION RECONCILIATION ===")
        print()
        print(f"  symbol: {position.symbol}")
        print(f"  side: {position.side.value}")
        print(f"  quantity: {position.quantity}")
        print(f"  entry_price: {position.entry_price}")
        print(f"  current_price: {position.current_price}")
        print(f"  stop_loss: {position.stop_loss}")
        print(f"  take_profit: {position.take_profit}")
        print(f"  unrealized_pnl: {position.unrealized_pnl}")

        print()
        print("DEMO EXECUTION: VERIFIED")
        return 0

    finally:
        await market_data_provider.disconnect()
        await execution_provider.disconnect()


async def run_runtime() -> None:
    """Build, start, and maintain the AtlasTrader runtime."""

    runtime_settings = RuntimeSettings()
    risk_settings = RiskSettings()
    mt5_settings = MT5Settings()

    symbols = runtime_settings.get_symbols()

    runtime: TradingRuntime = create_runtime(
        symbols=symbols,
        settings=risk_settings,
        mt5_settings=mt5_settings,
        balance=runtime_settings.initial_balance,
    )

    try:
        await runtime.start()
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        return
    finally:
        await runtime.stop()


def parse_args(
    argv: Sequence[str] | None = None,
) -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="AtlasTrader trading engine."
    )

    mode = parser.add_mutually_exclusive_group()

    mode.add_argument(
        "--preflight",
        action="store_true",
        help="Run the read-only MT5 readiness check.",
    )

    mode.add_argument(
        "--demo-order",
        action="store_true",
        help="Submit exactly one controlled XAUUSD demo order.",
    )

    parser.add_argument(
        "--side",
        type=parse_side,
        choices=list(OrderSide),
        help="Required direction for --demo-order: BUY or SELL.",
    )

    return parser.parse_args(argv)


async def main(
    argv: Sequence[str] | None = (),
) -> int:
    """Run AtlasTrader in the selected mode."""

    args = parse_args(argv)

    if args.preflight:
        return await run_preflight()

    if args.demo_order:
        if args.side is None:
            print(
                "Error: --demo-order requires --side BUY or --side SELL."
            )
            return 2

        return await run_demo_order(side=args.side)

    await run_runtime()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(None)))