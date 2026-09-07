from decimal import (
    Decimal,
    InvalidOperation,
)

from packages.core.enums import (
    OrderSide,
    SignalDirection,
)
from packages.core.trading_journal import (
    TradeDecision,
    TradeOutcome,
)
from packages.learning.models import (
    LearningRecord,
)


class LearningRecordBuilder:
    """Build strict one-to-one learning records from journal data."""

    def build(
        self,
        *,
        decision: TradeDecision,
        outcome: TradeOutcome,
    ) -> LearningRecord:
        """Join one approved decision to one realized outcome."""

        self._validate_lineage(
            decision=decision,
            outcome=outcome,
        )

        market_state = decision.market_state

        if decision.order_id is None:
            raise ValueError(
                "Learning decision requires order_id"
            )

        if decision.broker_order_id is None:
            raise ValueError(
                "Learning decision requires "
                "broker_order_id"
            )

        if decision.entry_price is None:
            raise ValueError(
                "Learning decision requires "
                "entry_price"
            )

        if decision.requested_quantity is None:
            raise ValueError(
                "Learning decision requires "
                "requested_quantity"
            )

        if outcome.exit_price is None:
            raise ValueError(
                "Learning outcome requires "
                "exit_price"
            )

        if outcome.closed_at is None:
            raise ValueError(
                "Learning outcome requires "
                "closed_at"
            )

        return LearningRecord(
            decision_id=decision.id,
            trade_id=outcome.trade_id,
            atlas_order_id=decision.order_id,
            broker_order_id=(
                decision.broker_order_id
            ),
            symbol=self._normalize_symbol(
                decision.symbol
            ),
            strategy=decision.strategy,
            timeframe=decision.timeframe,
            direction=decision.decision,
            side=outcome.side,
            decision_timestamp=(
                decision.timestamp
            ),
            opened_at=outcome.opened_at,
            closed_at=outcome.closed_at,
            signal_score=decision.signal_score,
            confidence=decision.confidence,
            requested_quantity=(
                decision.requested_quantity
            ),
            planned_entry_price=(
                decision.entry_price
            ),
            executed_entry_price=(
                outcome.entry_price
            ),
            exit_price=outcome.exit_price,
            stop_loss=decision.stop_loss,
            take_profit=decision.take_profit,
            risk_reward_ratio=(
                decision.risk_reward_ratio
            ),

            planned_risk_amount=(
            decision.risk_amount
            ),
            planned_risk_percentage=(
            decision.risk_percentage
            ),
            market_state_price=(
                self._decimal_feature(
                    market_state,
                    "price",
                )
            ),
            trend_score=self._float_feature(
                market_state,
                "trend_score",
            ),
            momentum_score=self._float_feature(
                market_state,
                "momentum_score",
            ),
            volatility_score=self._float_feature(
                market_state,
                "volatility_score",
            ),
            volatility=self._decimal_feature(
                market_state,
                "volatility",
            ),
            spread=self._decimal_feature(
                market_state,
                "spread",
            ),
            market_status=self._string_feature(
                market_state,
                "market_status",
            ),
            session=self._optional_string_feature(
                market_state,
                "session",
            ),
            is_tradeable=self._bool_feature(
                market_state,
                "is_tradeable",
            ),
            gross_pnl=outcome.gross_pnl,
            commission=outcome.commission,
            swap=outcome.swap,
            net_pnl=outcome.net_pnl,
            exit_reason=outcome.exit_reason,
            profitable=(
                outcome.net_pnl > Decimal(0)
            ),
        )

    def _validate_lineage(
        self,
        *,
        decision: TradeDecision,
        outcome: TradeOutcome,
    ) -> None:
        if decision.status != "approved":
            raise ValueError(
                "Learning records require "
                "an approved decision"
            )

        if (
            decision.decision
            is SignalDirection.FLAT
        ):
            raise ValueError(
                "Learning records require "
                "a directional decision"
            )

        if not outcome.realized:
            raise ValueError(
                "Learning records require "
                "a realized outcome"
            )

        if decision.broker_order_id is None:
            raise ValueError(
                "Learning decision requires "
                "broker_order_id"
            )

        if (
            len(
                outcome.entry_broker_order_ids
            )
            != 1
        ):
            raise ValueError(
                "Learning records currently require "
                "exactly one entry broker order"
            )

        outcome_broker_order_id = (
            outcome.entry_broker_order_ids[0]
        )

        if (
            decision.broker_order_id
            != outcome_broker_order_id
        ):
            raise ValueError(
                "Decision and outcome broker "
                "order identities do not match"
            )

        if (
            self._normalize_symbol(
                decision.symbol
            )
            != self._normalize_symbol(
                outcome.symbol
            )
        ):
            raise ValueError(
                "Decision and outcome symbols "
                "do not match"
            )

        expected_side = (
            OrderSide.BUY
            if (
                decision.decision
                is SignalDirection.LONG
            )
            else OrderSide.SELL
        )

        if outcome.side is not expected_side:
            raise ValueError(
                "Decision direction and outcome "
                "side do not match"
            )

    @staticmethod
    def _normalize_symbol(
        symbol: str,
    ) -> str:
        normalized = symbol.strip().upper()

        if not normalized:
            raise ValueError(
                "symbol must not be empty"
            )

        return normalized

    @staticmethod
    def _require_feature(
        data: dict[str, object],
        key: str,
    ) -> object:
        if key not in data:
            raise ValueError(
                f"Market-state feature missing: {key}"
            )

        return data[key]

    @classmethod
    def _decimal_feature(
        cls,
        data: dict[str, object],
        key: str,
    ) -> Decimal:
        raw = cls._require_feature(
            data,
            key,
        )

        try:
            return Decimal(
                str(raw)
            )
        except (
            InvalidOperation,
            ValueError,
        ) as exc:
            raise ValueError(
                f"Invalid decimal market-state "
                f"feature: {key}"
            ) from exc

    @classmethod
    def _float_feature(
        cls,
        data: dict[str, object],
        key: str,
    ) -> float:
        raw = cls._require_feature(
            data,
            key,
        )

        if isinstance(
            raw,
            bool,
        ):
            raise TypeError(
                f"Invalid float market-state "
                f"feature: {key}"
            )

        if not isinstance(
            raw,
            (
                str,
                int,
                float,
                Decimal,
            ),
        ):
            raise TypeError(
                f"Invalid float market-state "
                f"feature: {key}"
            )

        try:
            return float(raw)
        except ValueError as exc:
            raise ValueError(
                f"Invalid float market-state "
                f"feature: {key}"
            ) from exc

    @classmethod
    def _string_feature(
        cls,
        data: dict[str, object],
        key: str,
    ) -> str:
        raw = cls._require_feature(
            data,
            key,
        )

        if not isinstance(
            raw,
            str,
        ):
            raise TypeError(
                f"Invalid string market-state "
                f"feature: {key}"
            )

        value = raw.strip()

        if not value:
            raise ValueError(
                f"Empty string market-state "
                f"feature: {key}"
            )

        return value

    @classmethod
    def _optional_string_feature(
        cls,
        data: dict[str, object],
        key: str,
    ) -> str | None:
        raw = data.get(
            key
        )

        if raw is None:
            return None

        if not isinstance(
            raw,
            str,
        ):
            raise TypeError(
                f"Invalid string market-state "
                f"feature: {key}"
            )

        value = raw.strip()

        return value or None

    @classmethod
    def _bool_feature(
        cls,
        data: dict[str, object],
        key: str,
    ) -> bool:
        raw = cls._require_feature(
            data,
            key,
        )

        if not isinstance(
            raw,
            bool,
        ):
            raise TypeError(
                f"Invalid boolean market-state "
                f"feature: {key}"
            )

        return raw