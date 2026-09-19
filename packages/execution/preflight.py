from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from packages.core.models import (
    Instrument,
    MT5AccountSnapshot,
    MT5TerminalSnapshot,
    Position,
)
from packages.execution.mt5 import MT5ExecutionProvider
from packages.market_data.base import MarketDataProvider


@dataclass(slots=True)
class MT5PreflightResult:
    """Read-only readiness assessment for an MT5 trading environment."""

    terminal: MT5TerminalSnapshot
    account: MT5AccountSnapshot
    instruments: dict[str, Instrument] = field(default_factory=dict)
    positions: list[Position] = field(default_factory=list)
    quote_status: dict[str, bool] = field(default_factory=dict)
    checks: dict[str, bool] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        """Return whether all mandatory preflight checks passed."""
        return not self.blockers


class MT5Preflight:
    """Perform read-only readiness checks against MT5."""

    def __init__(
        self,
        *,
        execution_provider: MT5ExecutionProvider,
        market_data_provider: MarketDataProvider,
        symbols: list[str],
        max_quote_age_seconds: float = 60.0,
    ) -> None:
        normalized_symbols = list(dict.fromkeys(symbols))

        if not normalized_symbols:
            raise ValueError("At least one symbol is required")

        if max_quote_age_seconds <= 0:
            raise ValueError(
             "max_quote_age_seconds must be greater than zero"
        )

        self.execution_provider = execution_provider
        self.market_data_provider = market_data_provider
        self.symbols = normalized_symbols
        self.max_quote_age_seconds = max_quote_age_seconds

    async def run(self) -> MT5PreflightResult:
        """Run all read-only MT5 readiness checks."""
        if not await self.execution_provider.is_connected():
            raise RuntimeError(
                "Execution provider is not connected"
            )

        terminal = (
            await self.execution_provider.get_terminal_snapshot()
        )

        account = (
            await self.execution_provider.get_account_snapshot()
        )

        instruments: dict[str, Instrument] = {}
        blockers: list[str] = []
        checks: dict[str, bool] = {}

        checks["terminal_connected"] = terminal.connected

        if not terminal.connected:
            blockers.append("MT5 terminal is not connected")

        checks["terminal_trade_api_enabled"] = (
            not terminal.tradeapi_disabled
        )

        if terminal.tradeapi_disabled:
            blockers.append("MT5 trade API is disabled")

        checks["terminal_trade_allowed"] = terminal.trade_allowed

        if not terminal.trade_allowed:
            blockers.append(
                "MT5 terminal trading is disabled"
            )

        checks["account_trade_allowed"] = account.trade_allowed

        if not account.trade_allowed:
            blockers.append(
                "MT5 account trading is not allowed"
            )

        checks["account_trade_expert"] = account.trade_expert

        if not account.trade_expert:
            blockers.append(
                "MT5 account expert trading is not allowed"
            )

        checks["positive_equity"] = account.equity > Decimal(0)

        if account.equity <= Decimal(0):
            blockers.append("MT5 account equity is not positive")

        checks["positive_free_margin"] = (
            account.free_margin > Decimal(0)
        )

        if account.free_margin <= Decimal(0):
            blockers.append(
                "MT5 account has no free margin"
            )

        for symbol in self.symbols:
            try:
                instruments[symbol] = (
                    await self.execution_provider.get_instrument(symbol)
                )
                checks[f"instrument:{symbol}"] = (
                    instruments[symbol].enabled
                )

                if not instruments[symbol].enabled:
                    blockers.append(
                        f"Instrument is not enabled: {symbol}"
                    )
            except (KeyError, RuntimeError, ValueError) as exc:
                checks[f"instrument:{symbol}"] = False
                blockers.append(
                    f"Instrument check failed for {symbol}: {exc}"
                )

        positions = await self.execution_provider.get_positions()

        quote_status: dict[str, bool] = {}

        for symbol in self.symbols:
            try:
                quote = await self.market_data_provider.get_quote(
                    symbol
                )

                quote_valid = (
                    quote.bid > Decimal(0)
                    and quote.ask > Decimal(0)
                )

                if not quote_valid:
                    quote_status[symbol] = False
                    blockers.append(
                        f"Quote unavailable or invalid: {symbol}"
                    )
                else:
                    quote_age_seconds = (
                        datetime.now(UTC)
                        - quote.timestamp.astimezone(UTC)
                    ).total_seconds()

                    if quote_age_seconds < 0:
                       quote_status[symbol] = False
                       blockers.append(
                       f"Quote timestamp is in the future: {symbol}"
                    )
                    elif quote_age_seconds > self.max_quote_age_seconds:
                         quote_status[symbol] = False
                         blockers.append(
                         f"Quote is stale: {symbol}"
    )
                    else:
                        quote_status[symbol] = True

            except (KeyError, RuntimeError, ValueError):
                quote_status[symbol] = False
                blockers.append(
                    f"Quote unavailable or invalid: {symbol}"
                )

            checks[f"quote:{symbol}"] = quote_status[symbol]

        return MT5PreflightResult(
            terminal=terminal,
            account=account,
            instruments=instruments,
            positions=positions,
            quote_status=quote_status,
            checks=checks,
            blockers=blockers,
        )