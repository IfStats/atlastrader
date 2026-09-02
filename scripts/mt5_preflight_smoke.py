from __future__ import annotations

import asyncio

from packages.execution.mt5 import MT5ExecutionProvider
from packages.execution.preflight import MT5Preflight
from packages.market_data.mt5 import MT5MarketDataProvider


async def main() -> None:
    execution = MT5ExecutionProvider()
    market_data = MT5MarketDataProvider()

    await execution.connect()
    await market_data.connect()

    try:
        preflight = MT5Preflight(
            execution_provider=execution,
            market_data_provider=market_data,
            symbols=["EURUSD", "XAUUSD"],
        )

        result = await preflight.run()

        print("\n=== ATLASTRADER MT5 PREFLIGHT ===")

        print("\n--- TERMINAL ---")
        print(f"Connected:       {result.terminal.connected}")
        print(f"Trade allowed:   {result.terminal.trade_allowed}")
        print(
            f"Trade API off:   "
            f"{result.terminal.tradeapi_disabled}"
        )
        print(f"Build:           {result.terminal.build}")
        print(f"Name:            {result.terminal.name}")

        print("\n--- ACCOUNT ---")
        print(f"Login:           {result.account.login}")
        print(f"Server:          {result.account.server}")
        print(f"Currency:        {result.account.currency}")
        print(f"Balance:         {result.account.balance}")
        print(f"Equity:          {result.account.equity}")
        print(f"Margin:          {result.account.margin}")
        print(f"Free margin:     {result.account.free_margin}")
        print(f"Leverage:        {result.account.leverage}")
        print(
            f"Trade allowed:   "
            f"{result.account.trade_allowed}"
        )
        print(
            f"Trade expert:    "
            f"{result.account.trade_expert}"
        )

        print("\n--- INSTRUMENTS ---")
        for symbol, instrument in result.instruments.items():
            print(
                f"{symbol}: "
                f"enabled={instrument.enabled}, "
                f"min={instrument.min_volume}, "
                f"max={instrument.max_volume}, "
                f"step={instrument.volume_step}, "
                f"tick={instrument.tick_size}"
            )

        print("\n--- QUOTES ---")
        for symbol, healthy in result.quote_status.items():
            print(f"{symbol}: healthy={healthy}")

        print("\n--- POSITIONS ---")
        if result.positions:
            for position in result.positions:
                print(
                    f"{position.symbol}: "
                    f"{position.side.value}, "
                    f"quantity={position.quantity}, "
                    f"entry={position.entry_price}, "
                    f"current={position.current_price}, "
                    f"unrealized_pnl={position.unrealized_pnl}"
                )
        else:
            print("No open positions.")

        print("\n--- CHECKS ---")
        for name, passed in result.checks.items():
            status = "PASS" if passed else "FAIL"
            print(f"{status}: {name}")

        print("\n--- PREFLIGHT RESULT ---")

        if result.ready:
            print("READY")
            print("Read-only MT5 preflight passed.")
        else:
            print("BLOCKED")
            print("Read-only MT5 preflight failed.")
            print("\nBlockers:")
            for blocker in result.blockers:
                print(f"- {blocker}")

        print("\nORDER SUBMISSION: NOT PERFORMED")

    finally:
        await market_data.disconnect()
        await execution.disconnect()


if __name__ == "__main__":
    asyncio.run(main())