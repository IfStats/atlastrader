from collections import defaultdict

from packages.core.trading_journal import (
    TradeDecision,
    TradeOutcome,
)
from packages.learning.builder import (
    LearningRecordBuilder,
)
from packages.learning.models import (
    LearningDatasetAssembly,
    LearningRecord,
)


class LearningDatasetAssembler:
    """Assemble deterministic learning datasets from trade history."""

    def __init__(
        self,
        *,
        record_builder: LearningRecordBuilder | None = None,
    ) -> None:
        self.record_builder = (
            record_builder
            or LearningRecordBuilder()
        )

    def assemble(
        self,
        *,
        decisions: list[TradeDecision],
        outcomes: list[TradeOutcome],
    ) -> LearningDatasetAssembly:
        """Join decisions and outcomes using exact broker identities."""

        self._validate_unique_ids(
            decisions=decisions,
            outcomes=outcomes,
        )

        decisions_by_broker: dict[
            str,
            list[TradeDecision],
        ] = defaultdict(list)

        outcomes_by_broker: dict[
            str,
            list[TradeOutcome],
        ] = defaultdict(list)

        unmatched_decision_ids: list[str] = []
        unmatched_trade_ids: list[str] = []
        unsupported_trade_ids: list[str] = []

        blocked_broker_order_ids: set[str] = set()

        for decision in decisions:
            broker_order_id = (
                decision.broker_order_id
            )

            if broker_order_id is None:
                unmatched_decision_ids.append(
                    decision.id
                )
                continue

            normalized_id = self._normalize_broker_id(
                broker_order_id
            )

            decisions_by_broker[
                normalized_id
            ].append(
                decision
            )

        for outcome in outcomes:
            broker_order_ids = (
                outcome.entry_broker_order_ids
            )

            if not broker_order_ids:
                unmatched_trade_ids.append(
                    outcome.trade_id
                )
                continue

            normalized_ids = [
                self._normalize_broker_id(
                    broker_order_id
                )
                for broker_order_id
                in broker_order_ids
            ]

            if len(normalized_ids) != 1:
                unsupported_trade_ids.append(
                    outcome.trade_id
                )

                blocked_broker_order_ids.update(
                    normalized_ids
                )

                continue

            outcomes_by_broker[
                normalized_ids[0]
            ].append(
                outcome
            )

        records: list[LearningRecord] = []
        ambiguous_broker_order_ids: list[str] = []

        all_broker_order_ids = (
            set(decisions_by_broker)
            | set(outcomes_by_broker)
            | blocked_broker_order_ids
        )

        for broker_order_id in sorted(
            all_broker_order_ids
        ):
            if (
                broker_order_id
                in blocked_broker_order_ids
            ):
                ambiguous_broker_order_ids.append(
                    broker_order_id
                )
                continue

            broker_decisions = (
                decisions_by_broker.get(
                    broker_order_id,
                    [],
                )
            )

            broker_outcomes = (
                outcomes_by_broker.get(
                    broker_order_id,
                    [],
                )
            )

            if (
                len(broker_decisions) > 1
                or len(broker_outcomes) > 1
            ):
                ambiguous_broker_order_ids.append(
                    broker_order_id
                )
                continue

            if not broker_decisions:
                unmatched_trade_ids.extend(
                    outcome.trade_id
                    for outcome
                    in broker_outcomes
                )
                continue

            if not broker_outcomes:
                unmatched_decision_ids.extend(
                    decision.id
                    for decision
                    in broker_decisions
                )
                continue

            record = self.record_builder.build(
                decision=broker_decisions[0],
                outcome=broker_outcomes[0],
            )

            records.append(
                record
            )

        records.sort(
            key=lambda record: (
                record.decision_timestamp,
                record.decision_id,
            )
        )

        return LearningDatasetAssembly(
            records=records,
            unmatched_decision_ids=sorted(
                set(
                    unmatched_decision_ids
                )
            ),
            unmatched_trade_ids=sorted(
                set(
                    unmatched_trade_ids
                )
            ),
            ambiguous_broker_order_ids=sorted(
                set(
                    ambiguous_broker_order_ids
                )
            ),
            unsupported_trade_ids=sorted(
                set(
                    unsupported_trade_ids
                )
            ),
        )

    @staticmethod
    def _normalize_broker_id(
        broker_order_id: str,
    ) -> str:
        normalized = broker_order_id.strip()

        if not normalized:
            raise ValueError(
                "broker_order_id must not be blank"
            )

        return normalized

    @staticmethod
    def _validate_unique_ids(
        *,
        decisions: list[TradeDecision],
        outcomes: list[TradeOutcome],
    ) -> None:
        decision_ids = [
            decision.id
            for decision in decisions
        ]

        if (
            len(decision_ids)
            != len(set(decision_ids))
        ):
            raise ValueError(
                "Duplicate trade decision IDs "
                "are not allowed"
            )

        trade_ids = [
            outcome.trade_id
            for outcome in outcomes
        ]

        if (
            len(trade_ids)
            != len(set(trade_ids))
        ):
            raise ValueError(
                "Duplicate trade outcome IDs "
                "are not allowed"
            )