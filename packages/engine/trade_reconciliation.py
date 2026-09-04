from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from packages.core.enums import OrderSide, OrderStatus, TradeEntryType
from packages.core.models import BrokerDeal
from packages.core.trading_journal import TradeOutcome


class TradeOutcomeReconciler:
    """Convert broker entry/exit deals into realized trade outcomes."""

    def reconcile(
        self,
        deals: list[BrokerDeal],
    ) -> list[TradeOutcome]:
        """Reconcile complete broker positions into realized outcomes."""

        grouped: dict[str, list[BrokerDeal]] = defaultdict(list)

        for deal in deals:
            if deal.broker_position_id is None:
                raise ValueError(
                    f"Broker deal has no position ID: {deal.broker_deal_id}"
                )

            grouped[deal.broker_position_id].append(deal)

        outcomes: list[TradeOutcome] = []

        for position_id, position_deals in grouped.items():
            outcome = self._reconcile_position(
                position_id,
                position_deals,
            )

            if outcome is not None:
                outcomes.append(outcome)

        return outcomes

    def _reconcile_position(
        self,
        position_id: str,
        deals: list[BrokerDeal],
    ) -> TradeOutcome | None:
        entries = [
            deal
            for deal in deals
            if deal.entry_type is TradeEntryType.IN
        ]
        exits = [
            deal
            for deal in deals
            if deal.entry_type is TradeEntryType.OUT
        ]

        if not entries:
            raise ValueError(
                f"No entry deal found for position: {position_id}"
            )

        if not exits:
            return None

        entry_side = entries[0].side

        if any(deal.side is not entry_side for deal in entries):
            raise ValueError(
                f"Entry deals have inconsistent sides for position: "
                f"{position_id}"
            )

        expected_exit_side = (
            OrderSide.SELL
            if entry_side is OrderSide.BUY
            else OrderSide.BUY
        )

        if any(
            deal.side is not expected_exit_side
            for deal in exits
        ):
            raise ValueError(
                f"Exit deals have invalid side for position: "
                f"{position_id}"
            )

        entry_quantity = sum(
            (deal.quantity for deal in entries),
            Decimal(0),
        )
        exit_quantity = sum(
            (deal.quantity for deal in exits),
            Decimal(0),
        )

        if entry_quantity != exit_quantity:
            return None

        entry_price = self._weighted_average_price(entries)
        exit_price = self._weighted_average_price(exits)

        gross_pnl = sum(
            (deal.profit for deal in exits),
            Decimal(0),
        )
        commission = sum(
            (deal.commission for deal in deals),
            Decimal(0),
        )
        swap = sum(
            (deal.swap for deal in deals),
            Decimal(0),
        )
        net_pnl = gross_pnl + commission + swap

        opened_at = min(deal.timestamp for deal in entries)
        closed_at = max(deal.timestamp for deal in exits)

        exit_reason = self._infer_exit_reason(exits)

        return TradeOutcome(
            trade_id=position_id,
            symbol=entries[0].symbol,
            side=entry_side,
            order_status=OrderStatus.FILLED,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=entry_quantity,
            gross_pnl=gross_pnl,
            commission=commission,
            swap=swap,
            net_pnl=net_pnl,
            realized=True,
            opened_at=opened_at,
            closed_at=closed_at,
            exit_reason=exit_reason,
        )

    @staticmethod
    def _weighted_average_price(
        deals: list[BrokerDeal],
    ) -> Decimal:
        total_quantity = sum(
            (deal.quantity for deal in deals),
            Decimal(0),
        )

        if total_quantity <= 0:
            raise ValueError("Deal quantity must be greater than zero")

        weighted_value = sum(
            (deal.price * deal.quantity for deal in deals),
            Decimal(0),
        )

        return weighted_value / total_quantity

    @staticmethod
    def _infer_exit_reason(
        exits: list[BrokerDeal],
    ) -> str:
        comments = [
            deal.comment.strip().lower()
            for deal in exits
            if deal.comment
        ]

        if any("sl" in comment or "stop loss" in comment for comment in comments):
            return "stop_loss"

        if any("tp" in comment or "take profit" in comment for comment in comments):
            return "take_profit"

        return "broker_exit"